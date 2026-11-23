// Vẽ biểu đồ dashboard bằng Plotly từ API /api/stats/?period=week|month
(function () {
  var state = { period: "month", group: "day", cache: {} };
  var css = getComputedStyle(document.documentElement);
  var C = {
    ink: css.getPropertyValue("--ink").trim(), soft: css.getPropertyValue("--ink-soft").trim(),
    jade: css.getPropertyValue("--jade").trim(), sun: css.getPropertyValue("--sun").trim(),
    sky: css.getPropertyValue("--sky").trim(), line: css.getPropertyValue("--line").trim(),
  };
  var status = document.getElementById("chart-status");

  function baseLayout() {
    return {
      margin: { l: 44, r: 48, t: 10, b: 48 }, height: 320,
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "Be Vietnam Pro, system-ui, sans-serif", color: C.ink, size: 12 },
      legend: { orientation: "h", y: 1.14, x: 0 },
      xaxis: { gridcolor: C.line, tickangle: -35 },
      hovermode: "x unified",
    };
  }

  function draw(data) {
    var byWeek = state.group === "week" && state.period === "month";
    var rows = byWeek ? data.weekly : data.daily;
    var x = rows.map(function (r) { return r.label; });
    var mood = rows.map(function (r) { return byWeek ? r.avg_mood : r.mood; });
    var sleep = rows.map(function (r) { return byWeek ? r.avg_sleep_hours : r.sleep_hours; });
    var done = rows.map(function (r) { return r.habits_done; });
    var pct = rows.map(function (r) { return r.completion_percent; });
    var index = rows.map(function (r) { return r.wellbeing_index != null ? r.wellbeing_index : r.avg_wellbeing_index; });
    var coverage = rows.map(function (r) {
      return byWeek ? r.avg_wellbeing_index_coverage : r.wellbeing_index_coverage;
    });

    var layoutIndex = baseLayout();
    layoutIndex.yaxis = { title: "Chỉ số wellbeing", range: [0, 100], dtick: 20, gridcolor: C.line };
    Plotly.newPlot("chart-index", [
      { type: "scatter", mode: "lines+markers", x: x, y: index, name: "Chỉ số wellbeing",
        customdata: coverage, connectgaps: false, line: { color: C.jade, width: 3 }, marker: { size: 7 },
        hovertemplate: "%{y}/100<br>Độ phủ dữ liệu: %{customdata}%" },
    ], layoutIndex, { displayModeBar: false, responsive: true });

    var layout1 = baseLayout();
    layout1.yaxis = { title: "Tâm trạng (1-5)", range: [0.5, 5.5], dtick: 1, gridcolor: C.line };
    layout1.yaxis2 = { title: "Giờ ngủ", overlaying: "y", side: "right", range: [0, 12], showgrid: false };
    Plotly.newPlot("chart-mood", [
      { type: "bar", x: x, y: sleep, name: "Giờ ngủ", yaxis: "y2", marker: { color: C.sky, opacity: 0.35 }, hovertemplate: "%{y} giờ" },
      { type: "scatter", mode: "lines+markers", x: x, y: mood, name: "Tâm trạng", connectgaps: false,
        line: { color: C.jade, width: 3 }, marker: { size: 7 }, hovertemplate: "%{y}/5" },
    ], layout1, { displayModeBar: false, responsive: true });

    var layout2 = baseLayout();
    layout2.yaxis = { title: "Lượt hoàn thành", rangemode: "tozero", gridcolor: C.line, dtick: undefined };
    layout2.yaxis2 = { title: "% hoàn thành", overlaying: "y", side: "right", range: [0, 100], showgrid: false };
    Plotly.newPlot("chart-habits", [
      { type: "bar", x: x, y: done, name: "Thói quen đã làm", marker: { color: C.jade }, hovertemplate: "%{y} lượt" },
      { type: "scatter", mode: "lines+markers", x: x, y: pct, name: "% hoàn thành", yaxis: "y2",
        line: { color: C.sun, width: 3 }, marker: { size: 6 }, hovertemplate: "%{y}%" },
    ], layout2, { displayModeBar: false, responsive: true });

    var s = data.summary;
    status.textContent = "Từ " + s.start + " đến " + s.end + ": " + s.checkin_days + " ngày có check-in, " +
      s.habits_done + " lượt thói quen đã hoàn thành.";
  }

  function load() {
    var key = state.period;
    if (state.cache[key]) { draw(state.cache[key]); return; }
    status.textContent = "Đang tải số liệu…";
    fetch("/api/stats/?period=" + key, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); })
      .then(function (data) { state.cache[key] = data; draw(data); })
      .catch(function () { status.textContent = "Không tải được số liệu. Hãy tải lại trang hoặc đăng nhập lại."; });
  }

  function bind(attr, setter) {
    document.querySelectorAll("[" + attr + "]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        document.querySelectorAll("[" + attr + "]").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
        btn.setAttribute("aria-pressed", "true");
        setter(btn.getAttribute(attr));
        load();
      });
    });
  }
  bind("data-period", function (v) {
    state.period = v;
    if (v === "week") {
      state.group = "day";
      document.querySelectorAll("[data-group]").forEach(function (b) {
        b.setAttribute("aria-pressed", b.getAttribute("data-group") === "day" ? "true" : "false");
      });
    }
  });
  bind("data-group", function (v) { state.group = v; });
  load();
})();
