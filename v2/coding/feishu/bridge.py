"""桥：把事件变成动作，把动作变成回话。业务逻辑全在这里，可注入假实现来单测。"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from . import cards, config as fcfg, lark, ledger as fledger, notify, outbox, policy, triage

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RATE_PER_MIN = 10
RATE_PER_HOUR = 100

AUDIT = "audit/unauthorized.ndjson"
# 消息事件 key：policy.kind_of 按后缀认，含 "message.receive" 就算消息事件。
MESSAGE_KEY = "im.message.receive_v1"


def _iso(ts: float) -> str:
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(text: str) -> float:
    try:
        return _dt.datetime.fromisoformat(str(text).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _idem(prefix: str, *parts: str) -> str:
    """幂等键 ≤50 字，且截断时不能把有区分度的部分吃掉：超长就换成哈希。"""
    raw = ":".join([prefix, *[str(p) for p in parts]])
    if len(raw) <= 50:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix[:30]}:{digest}"[:50]


def _msg_time(raw: dict[str, Any]) -> float:
    """历史消息时间：create_time 可能是秒、毫秒或 ISO 字符串。"""
    for key in ("create_time", "createTime", "timestamp"):
        v = raw.get(key)
        if isinstance(v, (int, float)) and v > 0:
            return float(v) / 1000.0 if float(v) > 1e11 else float(v)
        if isinstance(v, str) and v.strip():
            try:
                return float(v) / 1000.0 if float(v) > 1e11 else float(v)
            except ValueError:
                parsed = _parse_iso(v)
                if parsed:
                    return parsed
    return 0.0


def _history_text(raw: dict[str, Any]) -> str:
    body = raw.get("body")
    content = body.get("content") if isinstance(body, dict) else raw.get("content")
    if not isinstance(content, str):
        return ""
    text = content.strip()
    if not text.startswith("{"):
        return text
    try:
        data = json.loads(text)
    except Exception:
        return ""
    return str(data.get("text") or "").strip() if isinstance(data, dict) else ""


def _slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^\w一-鿿-]+", "-", (text or "").strip())[:n].strip("-")
    return s or "untitled"


class Bridge:
    """一个桥实例管一台机器上的所有机器人。"""

    def __init__(self, root: "Path | str", cfg: "dict[str, Any] | None" = None,
                 ledger=None, sender: "Callable[..., Any] | None" = None,
                 wake_fn: "Callable[..., dict[str, Any]] | None" = None,
                 serve_fn: "Callable[..., tuple[bool, str]] | None" = None,
                 patcher: "Callable[..., tuple[bool, str]] | None" = None,
                 pin_fn: "Callable[..., Any] | None" = None,
                 now: "Callable[[], float] | None" = None):
        self.root = Path(root)
        self.cfg = cfg or fcfg.load(self.root)
        self.dir = self.root / ".coding" / "feishu"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._clock = now or time.time
        self.ledger = ledger or fledger.Ledger(self.dir / "ledger.sqlite3", clock=lambda: self.now())
        self.sender = sender
        self.patcher = patcher
        self.pin_fn = pin_fn
        self.wake_fn = wake_fn
        self.serve_fn = serve_fn
        self._last_wake: dict[str, float] = {}
        self._flush_lock = threading.Lock()
        self._secret = self._load_secret()

    def now(self) -> float:
        """时间源；测试可整体替换（账本也走它，别各用各的时钟）。"""
        return self._clock()

    # ── 密钥 ────────────────────────────────────────────────
    def _load_secret(self) -> str:
        p = self.dir / "secret.json"
        if p.is_file():
            try:
                return str(json.loads(p.read_text(encoding="utf-8")).get("secret") or "")
            except Exception:
                return ""
        secret = secrets.token_hex(16)
        try:
            p.write_text(json.dumps({"secret": secret}), encoding="utf-8")
            if os.name != "nt":
                os.chmod(p, 0o600)
        except Exception:
            pass
        return secret

    # ── 事件入口 ────────────────────────────────────────────
    def handle(self, ev: dict[str, Any]) -> "list[dict[str, Any]]":
        key = ev.get("dedup_key") or ""
        if not key:
            return []
        # 消息去重按机器人分开：多个机器人在同一个群被同时 @ 时，同一条 message_id
        # 对每个机器人都是「第一次见」，各该回各的。按钮动作不走这里——它由下方
        # act:<nonce> 全局去重，两个机器人不会把同一个门点批两次。
        if ev.get("kind") == "message":
            key = f"{ev.get('bot') or ''}|{key}"
        # 先鉴权再记账：未授权的人点了同一张卡，不能把共享的 nonce 消耗掉，
        # 否则他一次误点就能让主人的点击永远变成「已处理」。
        if not policy.allowed(self.cfg, ev):
            self._audit(ev)
            return []
        if not ev.get("backfilled") and not self._rate_ok(ev):
            # 补读不走限速：历史消息是成批回来的，限了会把它们丢掉且水位照样前进。
            self._audit(ev, decision="rate-limited")
            return []
        if not self.ledger.remember_event(key, ev.get("bot", ""), ev.get("kind", "")):
            # 重复事件不重复执行；按钮重复点给一句回执，消息重投保持安静。
            if ev.get("kind") == "card_action":
                # 用独立幂等键：否则「已处理。」会和第一次的回执撞键被队列吞掉。
                return [self._out(ev, text="已处理。", suffix=":dup")]
            return []
        if ev.get("kind") == "card_action":
            return self._on_action(ev)
        if ev.get("kind") != "message":
            return []
        return self._on_message(ev)

    def _rate_ok(self, ev: dict[str, Any]) -> bool:
        sender = str(ev.get("sender") or "")
        if not sender:
            return False
        minute = time.strftime("%Y%m%d%H%M", time.gmtime(self.now()))
        hour = minute[:10]
        if self.ledger.count(f"rate:{sender}", minute) >= RATE_PER_MIN:
            return False
        if self.ledger.count(f"rate:{sender}", hour) >= RATE_PER_HOUR:
            return False
        self.ledger.bump(f"rate:{sender}", minute, 1)
        self.ledger.bump(f"rate:{sender}", hour, 1)
        return True

    def _audit(self, ev: dict[str, Any], decision: str = "deny") -> None:
        p = self.dir / AUDIT
        p.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": self.now(), "dedup_key": ev.get("dedup_key"), "sender": ev.get("sender"),
               "chat_id": ev.get("chat_id"), "kind": ev.get("kind"),
               "chars": len(str(ev.get("text") or "")), "decision": decision}
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ── 消息 ────────────────────────────────────────────────
    def _on_message(self, ev: dict[str, Any]) -> "list[dict[str, Any]]":
        text = policy.strip_mentions(str(ev.get("text") or ""))
        d = triage.decide(text)
        kind = d["kind"]

        if kind == "status":
            return [self._out(ev, card=cards.board(notify.run_rows(self.root), "任务看板"))]
        if kind == "board":
            return [self._out(ev, card=cards.board(notify.run_rows(self.root)))]
        if kind == "idea":
            body = d["args"].get("text") or ""
            if not body:
                return [self._out(ev, text="想法是空的，没记。用「想法 <一句话>」。")]
            return [self._out(ev, text=self._save_idea(body))]
        if kind == "remember":
            return [self._out(ev, text=self._remember(d["args"].get("note") or "",
                                                      policy.binding_key(ev)))]
        if kind == "new_topic":
            self.ledger.drop_session(policy.binding_key(ev))
            return [self._out(ev, text="好，开个新话题。")]
        if kind == "ship_confirm":
            nonce = secrets.token_hex(8)
            return [self._out(ev, card=cards.ship_confirm(d["args"].get("run_id", ""), nonce))]
        if kind == "gate":
            return [self._out(ev, text=self._gate(d["args"]))]
        if kind == "stop":
            return [self._out(ev, text=self._stop(d["args"].get("run_id", "")))]
        return self._chat(ev, text, d)

    # ── 卡片按钮 ────────────────────────────────────────────
    def _on_action(self, ev: dict[str, Any]) -> "list[dict[str, Any]]":
        val = ev.get("action") or {}
        payload = {k: val.get(k) for k in ("kind", "run_id", "gate", "decision", "nonce")}
        sig = str(val.get("sig") or "")
        if not self._secret:
            return [self._out(ev, text="桥的签名密钥缺失，按钮暂时不可用（重发卡片会给新密钥）。")]
        if not policy.verify(self._secret, payload, sig):
            return [self._out(ev, text="这张卡的签名不对，已忽略。")]
        nk = f"act:{payload.get('nonce')}"
        if self.ledger.has_event(nk):
            return [self._out(ev, text="已处理。")]
        self.ledger.remember_event(nk, ev.get("bot", ""), "action")
        if payload.get("kind") == "noop":
            return [self._out(ev, text="好，先放着。")]
        if payload.get("kind") == "gate":
            # 同一个门点可能有好几张卡（原卡 + 多次提醒）。nonce 去重只挡同一张卡，
            # 这里按「run + 门」再挡一道，免得从两张不同的卡各批一次。
            gk = f"gate:{payload.get('run_id')}:{payload.get('gate')}"
            if self.ledger.has_event(gk):
                return [self._out(ev, text="这个门点已经拍过板了。", suffix=":dup")]
            self.ledger.remember_event(gk, ev.get("bot", ""), "gate")
            text = self._gate({"run_id": payload.get("run_id"),
                               "gate": payload.get("gate"),
                               "decision": payload.get("decision")})
            self._settle_card(payload, text)
            return [self._out(ev, text=text)]
        return [self._out(ev, text="这个按钮我不认识。")]

    def _settle_card(self, payload: dict[str, Any], text: str) -> None:
        """拍板后把同一 run + 门点的所有卡原地改成结果：群里不留还能点的旧卡。"""
        rid = str(payload.get("run_id") or "")
        gate = str(payload.get("gate") or "")
        done = "已提交" in text
        card = cards.card("已拍板" if done else "没生效", text,
                          template="green" if done else "grey")
        rows = self.ledger.cards_for(rid, gate) if rid else []
        rec = self.ledger.card_message(str(payload.get("nonce") or ""))
        if rec and not rows:
            rows = [rec]                             # 老数据没有 run/gate 字段时兜底
        seen = set()
        for row in rows:
            mid = str(row.get("message_id") or "")
            if not mid or mid in seen:
                continue
            seen.add(mid)
            prof = str(fcfg.bot_for(self.cfg, str(row.get("bot") or "")).get("profile") or "")
            self._patch(mid, card, prof)

    def _patch(self, message_id: str, card: dict[str, Any], profile: str = "") -> "tuple[bool, str]":
        if self.patcher is not None:
            return self.patcher(message_id, card, profile)
        try:
            r = lark.patch_card(profile, message_id, card)
        except Exception as e:                   # noqa: BLE001 —— 改卡失败不该影响回话
            return False, f"{type(e).__name__}: {e}"
        return getattr(r, "returncode", 1) == 0, (getattr(r, "stderr", "") or "").strip()[:300]

    # ── 执行面 ──────────────────────────────────────────────
    def _serve(self, path: str, body: dict[str, Any]) -> "tuple[bool, str]":
        if self.serve_fn is not None:
            return self.serve_fn(path, body)
        url = str((self.cfg.get("serve") or {}).get("url") or "http://127.0.0.1:8765").rstrip("/")
        token = os.environ.get(str((self.cfg.get("serve") or {}).get("token_env") or "KAI_TRAVEL_TOKEN"), "")
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url + path, data=data, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "X-Travel-Token": token})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body_text = r.read().decode("utf-8", errors="replace")
                try:
                    data = json.loads(body_text) if body_text.strip() else {}
                except Exception:
                    data = {}
                if isinstance(data, dict) and (data.get("error") or data.get("ok") is False):
                    return False, str(data.get("error") or "serve reported failure")
                return True, f"{r.status}"
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}"
        except Exception as e:
            return False, f"监工服务未启动（{e}）"

    def _gate(self, args: dict[str, Any]) -> str:
        rid, gate, decision = args.get("run_id"), args.get("gate") or "g2", args.get("decision")
        if not rid or not RUN_ID_RE.match(str(rid)):
            return "用法：批/拒 g0|g1|g2 <run>"
        if decision not in {"approve", "reject", "skip"}:
            return "用法：批/拒 g0|g1|g2 <run>"
        ok, msg = self._serve(f"/api/runs/{rid}/gate", {"gate": gate, "decision": decision})
        return f"{gate.upper()} {decision} → {'已提交' if ok else '失败：' + msg}"

    def _stop(self, rid: str) -> str:
        if not rid or not RUN_ID_RE.match(str(rid)):
            return "用法：停 <run>"
        ok, msg = self._serve(f"/api/runs/{rid}/stop", {})
        return "已停止。" if ok else f"停止失败：{msg}"

    def _save_idea(self, text: str) -> str:
        if not text:
            return "想法是空的，没记。"
        ideas = self._ideas_dir()
        ideas.mkdir(parents=True, exist_ok=True)
        day = _dt.date.today().isoformat()
        p = ideas / f"{day}-{_slug(text)}.md"
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"- {_dt.datetime.now().strftime('%H:%M')} {text}\n")
        return f"记进想法池了：`{p.name}`"

    def _remember(self, note: str, binding: str = "") -> str:
        if not note:
            return "要记住什么？"
        p = self.dir / "notes.md"
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"- {_dt.date.today().isoformat()} {note}\n")
        if binding:
            self.ledger.drop_session(binding)
        return "记住了，并开了新话题以免上下文越长越乱。"

    def _ideas_dir(self) -> Path:
        inst = self.root / ".ai" / "kai-mode.project.json"
        try:
            d = json.loads(inst.read_text(encoding="utf-8"))
            rel = ((d.get("paths") or {}).get("ideas_dir")) or "ideas"
        except Exception:
            rel = "ideas"
        return self.root / str(rel)

    # ── 对话 ────────────────────────────────────────────────
    def _chat(self, ev: dict[str, Any], text: str, d: dict[str, Any]) -> "list[dict[str, Any]]":
        if not self.cfg["chat"].get("enabled", True):
            return [self._out(ev, text="这句话我没有对应动作；对话模式当前关闭。试试「状态」或「曲速 …」。")]
        if self.wake_fn is None:
            return [self._out(ev, text="（桥没有配置唤醒实现，这条话没法处理）")]

        binding = policy.binding_key(ev)
        sess = self.ledger.session(binding)
        now = self.now()
        idle = float(self.cfg["chat"].get("idle_min", 45)) * 60
        if sess and now - float(sess.get("last_used") or 0) > idle:
            self.ledger.drop_session(binding)
            sess = None
        if sess and (int(sess.get("turns") or 0) >= int(self.cfg["chat"].get("max_turns", 20))
                     or int(sess.get("tokens") or 0) >= int(self.cfg["chat"].get("budget_tokens", 60000))):
            self.ledger.drop_session(binding)
            sess = None

        cooldown = float((self.cfg.get("wake") or {}).get("cooldown_s") or 0)
        last = self._last_wake.get(str(ev.get("sender") or ""), 0.0)
        if cooldown and now - last < cooldown:
            return [self._out(ev, text="慢一点，我正在处理上一条。")]
        daily = int(self.cfg["chat"].get("daily_budget_tokens", 200000))
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        if self.ledger.count("chat:tokens", day) >= daily:
            return [self._out(ev, text="今天的对话预算用完了；可以用「状态」或「曲速 …」这类指令继续。")]

        self._last_wake[str(ev.get("sender") or "")] = now
        brief = self._brief(ev, text, d)
        resume = (sess or {}).get("host_session") or None
        try:
            res = self.wake_fn(brief, str(self.root), resume)
        except Exception as e:
            return [self._out(ev, text=f"处理失败：{e}")]

        tokens = int(res.get("tokens") or 0)
        if res.get("session_id"):
            if sess:
                self.ledger.touch_session(binding, 1, tokens)
            else:
                self.ledger.bind_session(binding, ev.get("bot", ""), str(res["session_id"]),
                                         str(res.get("adapter") or ""))
                self.ledger.touch_session(binding, 1, tokens)
        if tokens:
            self.ledger.bump("chat:tokens", day, tokens)
        if res.get("over_budget"):
            # 一次唤醒就烧穿单次预算：这条会话别再续了，下条消息从干净上下文开始。
            self.ledger.drop_session(binding)
        reply = str(res.get("text") or "").strip() or "（没有输出）"
        return [self._out(ev, text=reply[:3000])]

    def _brief(self, ev: dict[str, Any], text: str, d: "dict[str, Any] | None" = None) -> str:
        notes = self.dir / "notes.md"
        tail = ""
        if notes.is_file():
            try:
                tail = "\n".join(notes.read_text(encoding="utf-8").splitlines()[-20:])
            except Exception:
                tail = ""
        intent = ""
        kind = (d or {}).get("kind")
        if kind == "ticket":
            intent = ("用户想开票。请把六件套（目标/AC/允许禁止/验证/依赖）补全后给一份草案；"
                      "缺的字段直接问，不要猜。\n\n")
        elif kind == "run":
            intent = ("用户想开 run。请把任务拆成 1-3 个可验收的子任务并给出任务图草案；"
                      "不要自己调用 travel。\n\n")
        return (
            "你是 kai-mode 在飞书里的对话面。用户在飞书里跟你说话；你看不到终端。\n"
            "只做两件事：回答、或把要做的事写成一句可执行的任务（别自己开 run）。\n"
            "不要编造状态；要看状态就用「状态」这条命令的路径。\n\n"
            + intent
            + f"用户：{text}\n\n"
            + (f"长期记忆（用户说过要记住的）：\n{tail}\n" if tail else "")
        )

    def _sign_card(self, card: "dict[str, Any] | None") -> "dict[str, Any] | None":
        """给卡片按钮加 HMAC 签名：没有签名的动作一律不执行。"""
        if not isinstance(card, dict) or not self._secret:
            return card
        for el in card.get("elements") or []:
            if not isinstance(el, dict) or el.get("tag") != "action":
                continue
            for a in el.get("actions") or []:
                v = a.get("value") if isinstance(a, dict) else None
                if isinstance(v, dict) and v.get("nonce"):
                    payload = {k: v.get(k) for k in ("kind", "run_id", "gate", "decision", "nonce")}
                    v["sig"] = policy.sign(self._secret, payload)
        return card

    # ── 出站 ────────────────────────────────────────────────
    def _out(self, ev: dict[str, Any], text: str = "", card: "dict[str, Any] | None" = None,
             suffix: str = "") -> dict[str, Any]:
        chat_id = ev.get("chat_id") or ""
        user_id = "" if chat_id else str(ev.get("sender") or "")      # 私聊没有 chat_id，用 open_id 发
        # 幂等键带机器人名与后缀：不同机器人的回话不能互相顶掉，
        # 后缀放在最前面，避免被 50 字上限截掉。
        idem = _idem(f"kaimode{suffix}", str(ev.get("bot") or ""), str(ev.get("dedup_key") or ""))
        return {"chat_id": chat_id, "user_id": user_id, "bot": ev.get("bot") or "",
                "message_id": ev.get("message_id") or "", "text": text, "idem": idem,
                "card": self._sign_card(card)}

    def deliver(self, out: dict[str, Any], profile: str = "") -> "tuple[bool, str]":
        if self.sender is not None:
            return self.sender(out, profile)
        idem = str(out.get("idem") or "")
        if out.get("card"):
            r = lark.send_card(profile, out.get("chat_id") or "", out["card"], idem,
                               user_id=out.get("user_id") or "")
        elif out.get("message_id"):
            r = lark.reply_text(profile, out["message_id"], out.get("text") or "", idem)
        else:
            r = lark.send_text(profile, out.get("chat_id") or "", out.get("text") or "", idem,
                               user_id=out.get("user_id") or "")
        ok = getattr(r, "returncode", 1) == 0
        if ok and out.get("card"):
            self._remember_card(out, r)
        return ok, (getattr(r, "stderr", "") or "").strip()[:300]

    def _remember_card(self, out: dict[str, Any], proc: Any) -> None:
        """记住发出去的卡片消息 id：拍板后要原地改成「已处理」。"""
        mid = lark.message_id_of(proc)
        if not mid:
            return
        for el in (out.get("card") or {}).get("elements") or []:
            if not isinstance(el, dict) or el.get("tag") != "action":
                continue
            for a in el.get("actions") or []:
                v = a.get("value") if isinstance(a, dict) else None
                if isinstance(v, dict) and v.get("nonce"):
                    self.ledger.remember_card(str(v["nonce"]), mid, str(out.get("bot") or ""),
                                              str(out.get("chat_id") or ""),
                                              str(v.get("run_id") or ""), str(v.get("gate") or ""))

    # ── 出站队列：先落库，再发；发失败的退避重试 ─────────────
    def enqueue(self, outs: "list[dict[str, Any]]") -> int:
        """把待发消息写进 sqlite；返回新入队条数（重复的幂等键不算）。"""
        n = 0
        for out in outs or []:
            if not (out.get("chat_id") or out.get("user_id")):
                continue
            idem = str(out.get("idem") or "") or f"adhoc:{secrets.token_hex(8)}"
            # 生成的幂等键要写回 payload：deliver 读的是 payload 里的 idem，
            # 不写回去重试时就会丢掉飞书侧的幂等键。
            payload = json.dumps({**out, "idem": idem}, ensure_ascii=False)
            if self.ledger.enqueue(idem, str(out.get("bot") or ""), str(out.get("chat_id") or ""),
                                   payload):
                n += 1
        return n

    def flush(self, limit: int = 20) -> "dict[str, int]":
        """发到点的行；多机器人各用各的 profile。

        多个 consumer 线程与主循环都会来要活：串行化，免得同一行被两条线同时发出。
        """
        with self._flush_lock:
            return outbox.flush(self.ledger, self.deliver, self.cfg, self.now(), limit)

    # ── 播报（状态变化）─────────────────────────────────────
    def tick(self) -> "list[dict[str, Any]]":
        """只看本轮有哪些播报，直接标记已播（不进队列；编排请用 publish）。"""
        outs, prev = self._scan()
        notify.save_snapshots(self.dir / "snapshots.json", prev)
        return outs

    def publish(self) -> "dict[str, int]":
        """播报的可靠路径：算卡片 → 落库 → 推进指纹 → 立刻试发一轮。

        顺序很关键：先入队再推进指纹。崩在两者之间时，下一轮会按旧指纹重新生成
        同样的卡片，幂等键相同，队列里已有就不会重复。
        """
        outs, prev = self._scan()
        n = self.enqueue(outs)
        notify.save_snapshots(self.dir / "snapshots.json", prev)
        stats = self.flush()
        stats["enqueued"] = n
        return stats

    def _scan(self) -> "tuple[list[dict[str, Any]], dict[str, Any]]":
        """算本轮该发哪些播报：带防抖（等状态稳定）与门点提醒（久等不批再喊一次）。

        快照按 run 记一个字典：fp（指纹）/ since（这次变化首次见到的时间）/
        sent（这一状态已播过）/ reminded（已提醒次数）/ last_remind。
        老版本快照里是纯字符串指纹，读进来时补成字典。
        """
        now = self.now()
        ncfg = self.cfg.get("notify") or {}
        debounce = float(ncfg.get("debounce_s") or 0)
        remind_min = float(ncfg.get("gate_reminder_min") or 0)
        max_rem = int(ncfg.get("max_reminders") or 0)

        prev = notify.load_snapshots(self.dir / "snapshots.json")
        rows = notify.run_rows(self.root)
        bot = fcfg.bot_for(self.cfg)
        chat = bot.get("chat_id") or ""
        outs: list[dict[str, Any]] = []
        seen = set()

        for row in rows:
            rid = row["run_id"]
            seen.add(rid)
            rec = prev.get(rid)
            if not isinstance(rec, dict):
                # 老版本快照里存的是纯字符串指纹，语义是「这个状态已经播过」。
                rec = {"fp": str(rec or ""), "since": 0.0, "sent": bool(rec),
                       "reminded": 0, "last_remind": 0.0}
            fp = notify.fingerprint(row)
            if rec.get("fp") != fp:
                rec = {"fp": fp, "since": now, "sent": False, "reminded": 0, "last_remind": 0.0}
                prev[rid] = rec
            if not notify.should_notify(row):
                prev.pop(rid, None)       # 不需要播报的阶段不占位，免得一直挂着
                continue
            if not chat:
                continue                  # 没落点：不推进快照，配上 chat_id 后补发
            kind = notify.kind_of(row)
            if not rec.get("sent"):
                if debounce > 0 and now - float(rec.get("since") or 0) < debounce:
                    continue              # 还在变，等它稳定下来再发
                outs.append(self._notify_out(row, kind, bot, fp))
                rec["sent"] = True
                rec["last_remind"] = now
                prev[rid] = rec
                continue
            # 门点一直挂着：隔一阵再喊一次，但不超过 max_reminders 次。
            if kind == "gate" and remind_min > 0 and int(rec.get("reminded") or 0) < max_rem:
                if now - float(rec.get("last_remind") or 0) >= remind_min * 60:
                    rec["reminded"] = int(rec.get("reminded") or 0) + 1
                    rec["last_remind"] = now
                    prev[rid] = rec
                    outs.append(self._notify_out(row, kind, bot, fp,
                                                 tag=f"r{rec['reminded']}", reminder=True))

        for rid in list(prev):
            if rid not in seen:
                prev.pop(rid, None)
        return outs, prev

    def _notify_out(self, row: dict[str, Any], kind: str, bot: dict[str, Any], fp: str,
                    tag: str = "", reminder: bool = False) -> dict[str, Any]:
        nonce = secrets.token_hex(8)
        name = str(bot.get("name") or "")
        prefix = f"kaimode{':' + tag if tag else ''}"
        return {"chat_id": bot.get("chat_id") or "", "bot": name,
                "message_id": "", "text": "",
                "idem": _idem(prefix, name, str(row["run_id"]), fp),
                "card": self._sign_card(notify.render(kind, row, nonce, reminder=reminder))}

    # ── 置顶看板：每个群发一次、置顶、之后原地刷新 ───────────
    def ensure_board(self) -> "dict[str, str]":
        """每个配了 chat_id 的机器人各有一块看板；返回 {机器人: 结果}。"""
        card = cards.board(notify.run_rows(self.root))
        out: dict[str, str] = {}
        for bot in self.cfg.get("bots") or []:
            chat = str(bot.get("chat_id") or "")
            if not chat:
                continue
            out[str(bot.get("name") or chat)] = self._ensure_one_board(bot, card)
        return out

    def _ensure_one_board(self, bot: dict[str, Any], card: dict[str, Any]) -> str:
        name = str(bot.get("name") or "")
        chat = str(bot.get("chat_id") or "")
        prof = str(bot.get("profile") or "")
        key = f"board:{name}:{chat}"
        misses = f"{key}:miss"
        pinned = f"{key}:pinned"
        old = self.ledger.meta_get(key)
        if old:
            ok, err = self._patch(old, card, prof)
            if ok:
                self.ledger.meta_del(misses)
                if self.ledger.meta_get(pinned, "1") != "1":
                    if self._pin(old, prof):
                        self.ledger.meta_set(pinned, "1")     # 上次没钉上，补钉
                        return "pinned"
                return "updated"
            # 一次失败可能只是网络：连续三次才认定这张卡没了，免得临时故障就再钉一块。
            n = int(self.ledger.meta_get(misses, "0") or 0) + 1
            self.ledger.meta_set(misses, str(n))
            if n < 3:
                return f"patch failed: {err}"
        ok, err, mid = self._send_card(prof, chat, card, _idem("kaimode:board", name))
        if not ok or not mid:
            return f"send failed: {err or 'no message_id'}"
        self.ledger.meta_set(key, mid)
        self.ledger.meta_del(misses)
        if old and old != mid:
            self._unpin(old, prof)          # 新板发成功才摘旧钉，中途断网至少还有一块
        if not self._pin(mid, prof):
            self.ledger.meta_set(pinned, "0")           # 下轮补钉
            return "sent but pin failed"
        self.ledger.meta_set(pinned, "1")
        return "pinned"

    def _pin(self, message_id: str, profile: str = "") -> bool:
        if self.pin_fn is not None:
            return bool(self.pin_fn(message_id, profile))
        try:
            r = lark.pin(profile, message_id)
        except Exception:                 # noqa: BLE001
            return False
        return getattr(r, "returncode", 1) == 0

    def _unpin(self, message_id: str, profile: str = "") -> None:
        try:
            lark.unpin(profile, message_id)
        except Exception:             # noqa: BLE001 —— 取旧钉失败不影响新看板
            pass

    def _send_card(self, profile: str, chat_id: str, card: dict[str, Any],
                   idem: str) -> "tuple[bool, str, str]":
        if self.sender is not None:
            ok, err = self.sender({"chat_id": chat_id, "card": card, "idem": idem,
                                   "bot": fcfg.bot_for(self.cfg).get("name", "")}, profile)
            return ok, err, ""
        try:
            r = lark.send_card(profile, chat_id, card, idem)
        except Exception as e:            # noqa: BLE001
            return False, f"{type(e).__name__}: {e}", ""
        return (getattr(r, "returncode", 1) == 0,
                (getattr(r, "stderr", "") or "").strip()[:300], lark.message_id_of(r))

    # ── 断线补读 ────────────────────────────────────────────
    def backfill(self) -> int:
        """桥没跑时用户发的消息，起来后补处理；首启只记水位，不回灌历史。

        只补「像指令」的群消息（命令/想法/批拒），旧闲聊不叫醒 AI。
        """
        cfg = self.cfg.get("backfill") or {}
        if not cfg.get("enabled", True):
            return 0
        now = self.now()
        limit = int(cfg.get("limit") or 50)
        max_min = float(cfg.get("max_min") or 180)
        chats = set((self.cfg.get("allow") or {}).get("chats") or [])
        total = 0
        for bot in self.cfg.get("bots") or []:
            chat = str(bot.get("chat_id") or "")
            if not chat or chat not in chats:
                continue
            key = f"backfill:{bot.get('name')}:{chat}"
            mark = self.ledger.meta_get(key)
            if not mark:
                self.ledger.meta_set(key, _iso(now))
                continue
            start = max(_parse_iso(mark), now - max_min * 60)
            try:
                items = lark.history_items(
                    lark.history(str(bot.get("profile") or ""), chat, _iso(start), limit))
            except Exception:               # noqa: BLE001 —— 补读失败不该拦住启动
                items = None
            if items is None:
                continue                    # 读失败 ≠ 没有消息：水位不动，下次再补
            for raw in items:
                ev = self._event_from_history(raw, chat, bot)
                if ev is None:
                    continue
                total += self.enqueue(self.handle(ev))
            # 只推进到这一页最新那条：积压超过一页时下次接着补，不跳过去。
            newest = max((_msg_time(x) for x in items), default=0.0)
            mark_next = newest if (len(items) >= limit and newest > 0) else now
            self.ledger.meta_set(key, _iso(max(mark_next, _parse_iso(mark))))
        if total:
            self.flush()
        return total

    def _event_from_history(self, raw: dict[str, Any], chat: str,
                            bot: dict[str, Any]) -> "dict[str, Any] | None":
        sender = raw.get("sender") if isinstance(raw.get("sender"), dict) else {}
        if str(sender.get("sender_type") or raw.get("sender_type") or "") in {"app", "bot"}:
            return None                                   # 不回自己的话
        sid = str(sender.get("id") or sender.get("open_id") or raw.get("sender_id") or "")
        mid = str(raw.get("message_id") or raw.get("open_message_id") or raw.get("id") or "")
        text = _history_text(raw)
        if not sid or not mid or not text:
            return None
        chat_type = str(raw.get("chat_type") or "group")
        # 分诊前先剥 @ 占位：历史里的正文是「@_user_1 状态」，不剥会被当成闲聊丢掉。
        if chat_type != "p2p" and triage.decide(policy.strip_mentions(text))["kind"] == "chat":
            return None                                   # 旧闲聊不叫醒 AI
        ev = policy.normalize(
            {"chat_id": chat, "chat_type": chat_type, "sender_id": sid, "message_id": mid,
             "content": text, "mentions": [m for m in (raw.get("mentions") or [])
                                           if isinstance(m, dict)]},
            MESSAGE_KEY, str(bot.get("name") or ""))
        if ev is not None:
            ev["backfilled"] = True
        return ev
