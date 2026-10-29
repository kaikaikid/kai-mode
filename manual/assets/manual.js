/* kai-mode 使用手册 —— 共享导航、主题与技能表 */

(function () {
  "use strict";

  var NAV = [
    {
      group: "上手",
      items: [
        ["index.html", "这是什么"],
        ["install.html", "装好它"],
      ],
    },
    {
      group: "日常",
      items: [
        ["tickets.html", "开票与施工"],
        ["progress.html", "看进度"],
        ["studio.html", "创作体系"],
        ["others.html", "其他能力"],
        ["troubleshooting.html", "遇到问题"],
      ],
    },
    {
      group: "参考",
      items: [
        ["skills.html", "技能速查"],
        ["plugins.html", "插件与装配"],
        ["assets/full-map.html", "完整技术图"],
      ],
    },
  ];

  function currentPage() {
    var name = location.pathname.split("/").pop();
    return name && name !== "" ? name : "index.html";
  }

  function renderNav() {
    var host = document.getElementById("side-nav");
    if (!host) return;
    var current = currentPage();
    var html = "";
    NAV.forEach(function (group) {
      html += '<div class="nav-group"><h2>' + group.group + "</h2>";
      group.items.forEach(function (item) {
        var href = item[0];
        var label = item[1];
        var currentAttr = href === current ? ' aria-current="page"' : "";
        html += '<a href="' + href + '"' + currentAttr + ">" + label + "</a>";
      });
      html += "</div>";
    });
    host.innerHTML = html;
  }

  function initTheme() {
    var key = "kai-manual-theme";
    var root = document.documentElement;
    var saved = null;
    try {
      saved = localStorage.getItem(key);
    } catch (e) {}
    if (!saved && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      saved = "dark";
    }
    if (saved === "dark") root.setAttribute("data-theme", "dark");

    var btn = document.getElementById("theme-btn");
    if (!btn) return;

    function label() {
      btn.textContent = root.getAttribute("data-theme") === "dark" ? "浅色" : "深色";
    }
    label();
    btn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem(key, next);
      } catch (e) {}
      label();
    });
  }

  function initMenu() {
    var btn = document.getElementById("menu-btn");
    var side = document.querySelector(".side");
    if (!btn || !side) return;
    btn.addEventListener("click", function () {
      side.classList.toggle("open");
      var open = side.classList.contains("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function initSkills() {
    var host = document.getElementById("skills-groups");
    var input = document.getElementById("skill-filter");
    var count = document.getElementById("skills-count");
    if (!host) return;

    var skills = window.KAI_SKILLS || [];
    var GROUPS = ["机场体系", "入口与安装", "文娱集团", "支持能力", "外部方法"];

    function rowHtml(s) {
      var version = s.version ? '<span class="badge">v' + escapeHtml(s.version) + "</span>" : "";
      var command = s.command ? "<code>" + escapeHtml(s.command) + "</code>" : '<span class="d-l">—</span>';
      return (
        "<tr>" +
        "<td>" + escapeHtml(s.plugin) + "</td>" +
        "<td><strong>" + escapeHtml(s.skill) + "</strong>" + version + "</td>" +
        "<td>" + escapeHtml(s.oneLine) + "</td>" +
        "<td>" + escapeHtml(s.trigger || "—") + "</td>" +
        "<td>" + command + "</td>" +
        "</tr>"
      );
    }

    function render(query) {
      var q = String(query || "").trim().toLowerCase();
      var filtered = skills.filter(function (s) {
        if (!q) return true;
        return [s.group, s.plugin, s.skill, s.oneLine, s.trigger, s.command, s.version]
          .join(" ")
          .toLowerCase()
          .indexOf(q) !== -1;
      });

      var byGroup = {};
      filtered.forEach(function (s) {
        var key = s.group || "其他";
        if (!byGroup[key]) byGroup[key] = [];
        byGroup[key].push(s);
      });

      var html = "";
      GROUPS.forEach(function (group) {
        var items = byGroup[group] || [];
        if (q && items.length === 0) return;
        var rows = items.map(rowHtml).join("");
        if (!rows) {
          rows = '<tr><td colspan="5" class="empty">这一类没有匹配的技能。</td></tr>';
        }
        html +=
          '<details class="skill-group" open>' +
          '<summary><span>' + escapeHtml(group) + '</span><span class="badge">' + items.length + "</span></summary>" +
          '<div class="table-wrap"><table>' +
          "<thead><tr><th>插件</th><th>技能</th><th>一句话</th><th>触发口令</th><th>命令</th></tr></thead>" +
          "<tbody>" + rows + "</tbody></table></div>" +
          "</details>";
      });

      host.innerHTML = html || '<p class="empty">没有匹配的技能，换个词试试。</p>';
      if (count) {
        count.textContent = "显示 " + filtered.length + " / " + skills.length + " 个技能";
      }
    }

    render("");
    if (input) {
      input.addEventListener("input", function () {
        render(input.value);
      });
    }
  }

  function init() {
    renderNav();
    initTheme();
    initMenu();
    initSkills();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
