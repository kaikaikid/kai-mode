"""桥：把事件变成动作，把动作变成回话。业务逻辑全在这里，可注入假实现来单测。"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from . import cards, config as fcfg, lark, ledger as fledger, notify, policy, triage

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RATE_PER_MIN = 10
RATE_PER_HOUR = 100

AUDIT = "audit/unauthorized.ndjson"


def _slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^\w一-鿿-]+", "-", (text or "").strip())[:n].strip("-")
    return s or "untitled"


class Bridge:
    """一个桥实例管一台机器上的所有机器人。"""

    def __init__(self, root: "Path | str", cfg: "dict[str, Any] | None" = None,
                 ledger=None, sender: "Callable[..., Any] | None" = None,
                 wake_fn: "Callable[..., dict[str, Any]] | None" = None,
                 serve_fn: "Callable[..., tuple[bool, str]] | None" = None,
                 now: "Callable[[], float] | None" = None):
        self.root = Path(root)
        self.cfg = cfg or fcfg.load(self.root)
        self.dir = self.root / ".coding" / "feishu"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._clock = now or time.time
        self.ledger = ledger or fledger.Ledger(self.dir / "ledger.sqlite3", clock=lambda: self.now())
        self.sender = sender
        self.wake_fn = wake_fn
        self.serve_fn = serve_fn
        self._last_wake: dict[str, float] = {}
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
        # 先鉴权再记账：未授权的人点了同一张卡，不能把共享的 nonce 消耗掉，
        # 否则他一次误点就能让主人的点击永远变成「已处理」。
        if not policy.allowed(self.cfg, ev):
            self._audit(ev)
            return []
        if not self._rate_ok(ev):
            self._audit(ev, decision="rate-limited")
            return []
        if not self.ledger.remember_event(key, ev.get("bot", ""), ev.get("kind", "")):
            # 重复事件不重复执行；按钮重复点给一句回执，消息重投保持安静。
            if ev.get("kind") == "card_action":
                return [self._out(ev, text="已处理。")]
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
            return [self._out(ev, text=self._gate({"run_id": payload.get("run_id"),
                                                   "gate": payload.get("gate"),
                                                   "decision": payload.get("decision")}))]
        return [self._out(ev, text="这个按钮我不认识。")]

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
    def _out(self, ev: dict[str, Any], text: str = "", card: "dict[str, Any] | None" = None) -> dict[str, Any]:
        chat_id = ev.get("chat_id") or ""
        user_id = "" if chat_id else str(ev.get("sender") or "")      # 私聊没有 chat_id，用 open_id 发
        idem = f"kaimode:{ev.get('dedup_key')}"[:50]
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
        return ok, (getattr(r, "stderr", "") or "").strip()[:300]

    # ── 播报（状态变化）─────────────────────────────────────
    def tick(self) -> "list[dict[str, Any]]":
        snap_path = self.dir / "snapshots.json"
        prev = notify.load_snapshots(snap_path)
        rows = notify.run_rows(self.root)
        outs = []
        for t in notify.transitions(prev, rows):
            row, fp, kind = t["row"], t["fingerprint"], t["kind"]
            if prev.get(row["run_id"]) == fp:
                continue
            nonce = secrets.token_hex(8)
            bot = fcfg.bot_for(self.cfg)
            out = {"chat_id": bot.get("chat_id") or "", "bot": bot.get("name") or "",
                   "message_id": "", "text": "",
                   "idem": f"kaimode:{row['run_id']}:{fp}",
                   "card": self._sign_card(notify.render(kind, row, nonce))}
            outs.append(out)
            prev[row["run_id"]] = fp
        notify.save_snapshots(snap_path, prev)
        return outs
