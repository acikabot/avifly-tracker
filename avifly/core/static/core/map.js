/*
 * Avifly maps (Leaflet): satellite + street layers, a field-location picker and a
 * read-only map of many points.
 *
 *   <div data-map-picker data-lat-input="id_latitude" data-lng-input="id_longitude"></div>
 *   <div data-map-points="points-json-id"></div>   (+ {{ points|json_script:"points-json-id" }})
 */
(function () {
  "use strict";

  var DEFAULT_CENTER = [41.6, 21.7]; // North Macedonia
  var DEFAULT_ZOOM = 8;

  function baseLayers() {
    var satellite = L.layerGroup([
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19,
        attribution: "Imagery &copy; Esri",
      }),
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19,
      }),
    ]);
    var streets = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    });
    return { Satellite: satellite, Map: streets };
  }

  function createMap(el) {
    var layers = baseLayers();
    var map = L.map(el, { layers: [layers.Satellite], scrollWheelZoom: false });
    L.control.layers(layers, null, { position: "topright" }).addTo(map);
    map.on("focus", function () { map.scrollWheelZoom.enable(); });
    return map;
  }

  function pointStyle(color, radius) {
    return { radius: radius || 8, color: "#fff", weight: 2, fillColor: color || "#2a78d6", fillOpacity: 0.85 };
  }

  function initPicker(el) {
    var latInput = document.getElementById(el.dataset.latInput);
    var lngInput = document.getElementById(el.dataset.lngInput);
    if (!latInput || !lngInput) return;
    var map = createMap(el);
    var marker = null;

    function current() {
      var lat = parseFloat(latInput.value);
      var lng = parseFloat(lngInput.value);
      return isNaN(lat) || isNaN(lng) ? null : [lat, lng];
    }

    function place(latlng, pan) {
      if (!marker) marker = L.circleMarker(latlng, pointStyle("#dc3545")).addTo(map);
      else marker.setLatLng(latlng);
      if (pan) map.setView(latlng, Math.max(map.getZoom(), 15));
    }

    var start = current();
    if (start) {
      map.setView(start, 16);
      place(start, false);
    } else {
      map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
    }

    map.on("click", function (e) {
      latInput.value = e.latlng.lat.toFixed(6);
      lngInput.value = e.latlng.lng.toFixed(6);
      place(e.latlng, false);
    });

    function onInput() {
      var point = current();
      if (point) place(point, true);
    }
    latInput.addEventListener("change", onInput);
    lngInput.addEventListener("change", onInput);
  }

  function initPoints(el) {
    var source = document.getElementById(el.dataset.mapPoints);
    var points = source ? JSON.parse(source.textContent) : [];
    var map = createMap(el);
    var bounds = [];
    points.forEach(function (p) {
      var marker = L.circleMarker([p.lat, p.lng], pointStyle(p.color, p.radius)).addTo(map);
      var html = document.createElement("div");
      var title = document.createElement(p.url ? "a" : "strong");
      title.textContent = p.label;
      if (p.url) title.href = p.url;
      html.appendChild(title);
      if (p.detail) {
        var detail = document.createElement("div");
        detail.className = "small text-body-secondary";
        detail.textContent = p.detail;
        html.appendChild(detail);
      }
      marker.bindPopup(html);
      bounds.push([p.lat, p.lng]);
    });
    if (bounds.length === 1) map.setView(bounds[0], 15);
    else if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
    else map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (typeof L === "undefined") return;
    document.querySelectorAll("[data-map-picker]").forEach(initPicker);
    document.querySelectorAll("[data-map-points]").forEach(initPoints);
  });
})();
