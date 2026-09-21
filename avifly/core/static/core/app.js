/*
 * Avifly — small progressive enhancements shared by every page.
 * Every page works without this file; it only makes things quicker on a phone.
 */
(function () {
  "use strict";

  var avifly = (window.avifly = window.avifly || {});

  avifly.csrfToken = function () {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  };

  avifly.postForm = function (url, data) {
    var body = new FormData();
    Object.keys(data).forEach(function (key) {
      if (data[key] !== null && data[key] !== undefined) body.append(key, data[key]);
    });
    return fetch(url, {
      method: "POST",
      body: body,
      credentials: "same-origin",
      headers: { "X-CSRFToken": avifly.csrfToken(), "X-Requested-With": "fetch" },
    }).then(function (response) {
      return response.json().then(function (json) {
        return { ok: response.ok, data: json };
      });
    });
  };

  function pad(n) {
    return (n < 10 ? "0" : "") + n;
  }

  avifly.nowTime = function () {
    var d = new Date();
    return pad(d.getHours()) + ":" + pad(d.getMinutes());
  };

  avifly.today = function () {
    var d = new Date();
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  };

  function fire(el, type) {
    el.dispatchEvent(new Event(type, { bubbles: true }));
  }
  avifly.fire = fire;

  /* ---- search that ignores the alphabet (mirrors avifly/core/text.py) ------------------- */
  var CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ѓ": "gj", "ђ": "gj", "е": "e", "ж": "zh",
    "з": "z", "ѕ": "dz", "и": "i", "ј": "j", "к": "k", "л": "l", "љ": "lj", "м": "m", "н": "n",
    "њ": "nj", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "ќ": "kj", "ћ": "kj", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "џ": "dzh", "ш": "sh",
    "ž": "zh", "š": "sh", "č": "ch", "ć": "kj", "đ": "gj", "ǵ": "gj", "ḱ": "kj",
  };
  var LOOSE = [["dzh", "dz"], ["zh", "z"], ["sh", "s"], ["ch", "c"], ["kj", "k"], ["gj", "g"], ["lj", "l"], ["nj", "n"]];

  avifly.normalize = function (text) {
    var out = "";
    var lower = String(text || "").toLowerCase();
    for (var i = 0; i < lower.length; i++) {
      var ch = lower[i];
      out += CYRILLIC[ch] !== undefined ? CYRILLIC[ch] : ch.normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
    }
    LOOSE.forEach(function (pair) { out = out.split(pair[0]).join(pair[1]); });
    return out.replace(/[^a-z0-9]+/g, " ").trim();
  };

  function alphabetBlindScore(search) {
    var terms = avifly.normalize(search).split(" ").filter(Boolean);
    return function (item) {
      if (!terms.length) return 1;
      var text = avifly.normalize(item.text);
      for (var i = 0; i < terms.length; i++) {
        if (text.indexOf(terms[i]) === -1) return 0;
      }
      return 1;
    };
  }

  /* ---- searchable dropdowns (Tom Select) ------------------------------------------- */
  avifly.initSelect = function (select) {
    if (select.tomselect || typeof TomSelect === "undefined") return;
    var plugins = select.multiple ? ["remove_button"] : [];
    if (!select.multiple && !select.required) plugins.push("clear_button");
    var options = {
      plugins: plugins,
      maxOptions: 500,
      allowEmptyOption: false, // the empty option becomes the placeholder
      score: alphabetBlindScore,
    };
    if (select.dataset.placeholder) options.placeholder = select.dataset.placeholder;
    new TomSelect(select, options);
  };

  avifly.setSelectOptions = function (select, items, keepSelected) {
    /* Replace a select's options with [{value, text, group}] and keep valid selections. */
    var selected = Array.prototype.map.call(select.selectedOptions, function (o) { return o.value; });
    var ts = select.tomselect;
    if (ts) {
      ts.clear(true);
      ts.clearOptions();
      items.forEach(function (item) { ts.addOption({ value: String(item.value), text: item.text }); });
      ts.refreshOptions(false);
      if (keepSelected) {
        selected.forEach(function (v) { if (ts.options[v]) ts.addItem(v, true); });
      }
      return;
    }
    select.innerHTML = "";
    if (!select.multiple) select.add(new Option("---------", ""));
    items.forEach(function (item) {
      var opt = new Option(item.text, item.value);
      opt.selected = keepSelected && selected.indexOf(String(item.value)) !== -1;
      select.add(opt);
    });
  };

  /* ---- "now" buttons: fill a time/date input with the current time ---------------- */
  function fillNow(button) {
    var input = document.getElementById(button.dataset.fillNow);
    if (!input) return;
    input.value = input.type === "date" ? avifly.today() : avifly.nowTime();
    fire(input, "input");
    fire(input, "change");
  }

  /* ---- location ---------------------------------------------------------------------- */
  function setCoords(lat, lng, latTarget, lngTarget) {
    var latInput = document.getElementById(latTarget);
    var lngInput = document.getElementById(lngTarget);
    if (!latInput || !lngInput) return;
    latInput.value = Number(lat).toFixed(6);
    lngInput.value = Number(lng).toFixed(6);
    fire(latInput, "change");
    fire(lngInput, "change");
  }

  function geolocate(button) {
    if (!window.isSecureContext || !navigator.geolocation) {
      alert(button.dataset.insecureMessage || "Your location is only available over HTTPS.");
      return;
    }
    button.disabled = true;
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        button.disabled = false;
        setCoords(pos.coords.latitude, pos.coords.longitude, button.dataset.latTarget, button.dataset.lngTarget);
      },
      function (err) {
        button.disabled = false;
        alert(err.message);
      },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  }

  /* Accepts "41.99646, 21.43141", "41.99646 21.43141" or a Google Maps link (…@41.99,21.43…). */
  avifly.parseCoords = function (text) {
    var match = /@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/.exec(text) ||
      /(-?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)/.exec(text);
    if (!match) return null;
    var lat = parseFloat(match[1]);
    var lng = parseFloat(match[2]);
    if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
    return { lat: lat, lng: lng };
  };

  function onCoordsPaste(input) {
    var coords = avifly.parseCoords(input.value);
    if (coords) {
      setCoords(coords.lat, coords.lng, input.dataset.latTarget, input.dataset.lngTarget);
      input.classList.remove("is-invalid");
    } else if (input.value.trim()) {
      input.classList.add("is-invalid");
    }
  }

  /* ---- wiring -------------------------------------------------------------------------- */
  avifly.init = function (root) {
    root = root || document;
    root.querySelectorAll("select[data-tom]").forEach(avifly.initSelect);
  };

  document.addEventListener("click", function (event) {
    var nowButton = event.target.closest("[data-fill-now]");
    if (nowButton) {
      event.preventDefault();
      fillNow(nowButton);
      return;
    }
    var geoButton = event.target.closest("[data-geolocate]");
    if (geoButton) {
      event.preventDefault();
      geolocate(geoButton);
      return;
    }
    var confirmEl = event.target.closest("a[data-confirm], button[data-confirm]");
    if (confirmEl && !window.confirm(confirmEl.dataset.confirm)) {
      event.preventDefault();
    }
  });

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });

  document.addEventListener("change", function (event) {
    var el = event.target;
    if (el.matches("[data-coords-paste]")) onCoordsPaste(el);
    var form = el.closest("form[data-autosubmit]");
    if (form && el.matches("select, input[type=date], input[type=checkbox]")) form.requestSubmit();
  });

  document.addEventListener("DOMContentLoaded", function () {
    avifly.init(document);
  });
  document.addEventListener("htmx:load", function (event) {
    avifly.init(event.detail.elt);
  });
})();
