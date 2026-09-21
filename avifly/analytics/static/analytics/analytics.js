/*
 * Analytics charts (ECharts). Chart data comes from the page as JSON; every chart
 * also has a table view in the page, so nothing depends on hovering.
 *
 * Styling follows one set of rules: categorical colours in a fixed order (validated
 * for colour-blind separation), thin marks, hairline grid, text in ink colours only.
 */
(function () {
  "use strict";

  var SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
  var SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]; // blue 100→700
  var INK = {
    primary: "#0b0b0b",
    secondary: "#52514e",
    muted: "#898781",
    grid: "#e1e0d9",
    axis: "#c3c2b7",
    surface: "#ffffff",
    border: "rgba(11,11,11,0.10)",
  };
  var FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

  var container = document.getElementById("charts");
  var source = document.getElementById("chart-data");
  if (!container || !source || typeof echarts === "undefined") return;
  var currency = container.dataset.currency || "";
  var data = JSON.parse(source.textContent);
  var instances = [];

  /* ---- number formatting ---------------------------------------------------------- */
  function number(value, places) {
    return Number(value).toLocaleString("en-US", { minimumFractionDigits: places, maximumFractionDigits: places });
  }

  function format(value, unit) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    switch (unit) {
      case "money": return number(Math.round(value), 0) + " " + currency;
      case "money_per_ha": return number(Math.round(value), 0) + " " + currency + "/ha";
      case "ha": return number(value, 1) + " ha";
      case "ha_per_hour": return number(value, 1) + " ha/h";
      default: return number(value, 0);
    }
  }

  function compact(value) {
    var abs = Math.abs(value);
    if (abs >= 1e6) return number(value / 1e6, abs % 1e6 === 0 ? 0 : 1) + "M";
    if (abs >= 1e4) return number(value / 1e3, 0) + "K";
    return number(value, abs < 10 && abs % 1 !== 0 ? 1 : 0);
  }

  function colour(slot) {
    return slot === "muted" ? INK.muted : SERIES[slot % SERIES.length];
  }

  /* ---- tooltips: built with textContent (labels are user data) ------------------- */
  function tooltipBox(title, rows) {
    var box = document.createElement("div");
    var head = document.createElement("div");
    head.style.cssText = "color:" + INK.secondary + ";margin-bottom:4px";
    head.textContent = title;
    box.appendChild(head);
    rows.forEach(function (row) {
      var line = document.createElement("div");
      line.style.cssText = "display:flex;align-items:center;gap:8px";
      if (row.colour) {
        var key = document.createElement("span");
        key.style.cssText = "display:inline-block;width:12px;height:2px;background:" + row.colour;
        line.appendChild(key);
      }
      var value = document.createElement("strong");
      value.style.color = INK.primary;
      value.textContent = row.value;
      line.appendChild(value);
      if (row.label) {
        var label = document.createElement("span");
        label.style.color = INK.secondary;
        label.textContent = row.label;
        line.appendChild(label);
      }
      box.appendChild(line);
    });
    return box;
  }

  function baseTooltip(extra) {
    var tooltip = {
      backgroundColor: INK.surface,
      borderColor: INK.border,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: INK.primary, fontFamily: FONT, fontSize: 12 },
      extraCssText: "box-shadow:0 2px 8px rgba(0,0,0,.08);border-radius:6px;",
      confine: true,
    };
    return Object.assign(tooltip, extra || {});
  }

  function base(hasLegend) {
    return {
      animationDuration: 300,
      textStyle: { fontFamily: FONT, color: INK.secondary, fontSize: 12 },
      grid: { left: 4, right: 16, top: hasLegend ? 36 : 12, bottom: 4, containLabel: true },
      legend: hasLegend
        ? { top: 0, left: 0, itemWidth: 14, itemHeight: 10, textStyle: { color: INK.secondary, fontFamily: FONT } }
        : { show: false },
    };
  }

  function categoryAxis(categories) {
    return {
      type: "category",
      data: categories,
      axisLine: { lineStyle: { color: INK.axis, width: 1 } },
      axisTick: { show: false },
      axisLabel: { color: INK.muted, hideOverlap: true },
    };
  }

  function valueAxis() {
    return {
      type: "value",
      axisLabel: { color: INK.muted, formatter: compact },
      splitLine: { lineStyle: { color: INK.grid, width: 1, type: "solid" } },
      axisLine: { show: false },
      axisTick: { show: false },
    };
  }

  /* ---- chart kinds ------------------------------------------------------------------ */
  function seriesOption(s, count) {
    var c = colour(s.slot);
    if (s.type === "bar") {
      return {
        name: s.name,
        type: "bar",
        data: s.data,
        stack: s.stack,
        barMaxWidth: 24,
        barGap: "0%",
        itemStyle: {
          color: c,
          borderRadius: s.stack ? 0 : [4, 4, 0, 0],
          borderColor: INK.surface,
          borderWidth: 1, // 1px each side = the 2px surface gap between touching bars
        },
        emphasis: { itemStyle: { opacity: 0.85 } },
      };
    }
    var line = {
      name: s.name,
      type: "line",
      data: s.data,
      symbol: "circle",
      symbolSize: 8,
      showSymbol: s.data.length <= 16,
      connectNulls: false,
      lineStyle: { width: 2, color: c, cap: "round", join: "round" },
      itemStyle: { color: c, borderColor: INK.surface, borderWidth: 2 },
      z: 3,
    };
    if (count === 1) line.areaStyle = { color: c, opacity: 0.1 };
    return line;
  }

  function axisChart(chart) {
    var hasLegend = chart.series.length >= 2;
    var option = base(hasLegend);
    option.xAxis = categoryAxis(chart.categories);
    option.yAxis = valueAxis();
    option.series = chart.series.map(function (s) { return seriesOption(s, chart.series.length); });
    if (chart.zero_line && option.series.length) {
      option.series[option.series.length - 1].markLine = {
        silent: true,
        symbol: "none",
        label: { show: false },
        lineStyle: { color: INK.axis, width: 1, type: "solid" },
        data: [{ yAxis: 0 }],
      };
    }
    option.tooltip = baseTooltip({
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: INK.axis, width: 1 } },
      formatter: function (params) {
        var rows = params
          .filter(function (p) { return p.value !== null && p.value !== undefined; })
          .map(function (p) { return { colour: p.color, value: format(p.value, chart.unit), label: p.seriesName }; });
        return tooltipBox(params.length ? params[0].axisValueLabel : "", rows);
      },
    });
    return option;
  }

  var measure = document.createElement("canvas").getContext("2d");
  function textWidth(text) {
    measure.font = "12px " + FONT;
    return measure.measureText(String(text)).width;
  }

  function widest(texts) {
    return texts.reduce(function (max, t) { return Math.max(max, textWidth(t)); }, 0);
  }

  function hbarChart(chart, el) {
    // Largest at the top: ECharts draws category axes bottom-up.
    var categories = chart.categories.slice().reverse();
    var values = chart.values.slice().reverse();
    var details = (chart.details || []).slice().reverse();
    el.style.height = Math.max(140, categories.length * 34 + 30) + "px";
    // Room for the names on the left and the value at each bar's tip, measured so
    // neither is cut off; long names are shortened (full name in the tooltip/table).
    var width = el.clientWidth || 320;
    var labelWidth = Math.min(Math.ceil(widest(categories)) + 4, Math.round(width * 0.38));
    var valueWidth = Math.ceil(widest(values.map(function (v) { return format(v, chart.unit); }))) + 12;
    var option = base(false);
    option.grid = { left: labelWidth + 10, right: valueWidth, top: 4, bottom: 4, containLabel: false };
    option.xAxis = Object.assign(valueAxis(), { axisLabel: { show: false }, splitLine: { show: false } });
    option.yAxis = Object.assign(categoryAxis(categories), {
      axisLabel: { color: INK.secondary, width: labelWidth, overflow: "truncate", margin: 8 },
    });
    option.series = [
      {
        type: "bar",
        data: values,
        barMaxWidth: 24,
        itemStyle: { color: SERIES[0], borderRadius: [0, 4, 4, 0] },
        emphasis: { itemStyle: { opacity: 0.85 } },
        label: {
          show: true,
          position: "right",
          color: INK.secondary,
          formatter: function (p) { return format(p.value, chart.unit); },
        },
      },
    ];
    option.tooltip = baseTooltip({
      trigger: "item",
      formatter: function (p) {
        var rows = [{ colour: SERIES[0], value: format(p.value, chart.unit) }];
        if (details[p.dataIndex]) rows.push({ value: "", label: details[p.dataIndex] });
        return tooltipBox(p.name, rows);
      },
    });
    return option;
  }

  function calendarChart(chart, el) {
    var narrow = el.clientWidth < 640;
    el.style.height = narrow ? "560px" : "210px";
    var option = base(false);
    option.calendar = {
      range: String(chart.year),
      orient: narrow ? "vertical" : "horizontal",
      top: narrow ? 30 : 36,
      left: narrow ? 40 : 30,
      right: 10,
      bottom: narrow ? 10 : 40,
      cellSize: narrow ? ["auto", 9] : ["auto", 16],
      splitLine: { show: false },
      itemStyle: { color: "#f4f5f7", borderColor: INK.surface, borderWidth: 2 },
      dayLabel: { firstDay: 1, nameMap: "en", color: INK.muted, fontSize: 10 },
      monthLabel: { color: INK.muted, fontSize: 11 },
      yearLabel: { show: false },
    };
    option.visualMap = {
      min: 0,
      max: Math.max(chart.max, 1),
      calculable: false,
      orient: "horizontal",
      left: narrow ? 40 : 30,
      bottom: narrow ? "auto" : 0,
      top: narrow ? 0 : "auto",
      itemWidth: 10,
      itemHeight: 120,
      text: [format(chart.max, "ha"), "0"],
      textStyle: { color: INK.muted, fontSize: 11 },
      inRange: { color: SEQUENTIAL },
    };
    option.series = [
      {
        type: "heatmap",
        coordinateSystem: "calendar",
        data: chart.days,
        emphasis: { itemStyle: { borderColor: INK.primary, borderWidth: 1 } },
      },
    ];
    option.tooltip = baseTooltip({
      trigger: "item",
      formatter: function (p) {
        var date = new Date(p.value[0] + "T00:00:00");
        var title = date.toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short" });
        return tooltipBox(title, [{ colour: SEQUENTIAL[4], value: format(p.value[1], "ha") }]);
      },
    });
    return option;
  }

  function build(el) {
    var chart = data[el.dataset.chart];
    if (!chart) return;
    var option;
    if (chart.kind === "hbar") option = hbarChart(chart, el);
    else if (chart.kind === "calendar") option = calendarChart(chart, el);
    else option = axisChart(chart);
    var instance = echarts.init(el, null, { renderer: "canvas" });
    instance.setOption(option);
    instances.push(instance);
  }

  document.addEventListener("DOMContentLoaded", function () {
    container.querySelectorAll("[data-chart]").forEach(build);
  });

  var resizeTimer = null;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      instances.forEach(function (instance) { instance.resize(); });
    }, 150);
  });
})();
