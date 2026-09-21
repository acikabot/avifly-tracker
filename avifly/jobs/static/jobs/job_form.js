/*
 * Job form: live price, customer → fields and default rate, multi-day toggle,
 * quick "new customer" / "new field" dialogs. The form still works without it.
 */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("job-form");
    if (!form) return;
    var avifly = window.avifly;

    var ratesEl = document.getElementById("operation-rates");
    var rates = ratesEl ? JSON.parse(ratesEl.textContent) : {};
    var customerSelect = document.getElementById("id_job-customer");
    var operationSelect = document.getElementById("id_job-operation_type");
    var rateInput = document.getElementById("id_job-rate_per_ha");
    var multiToggle = document.getElementById("id_job-is_multi_day");
    var rateTouched = form.dataset.rateSet === "1";
    var specialRate = null;
    var quickFieldTarget = null;

    function num(value) {
      var n = parseFloat(String(value || "").replace(",", "."));
      return isNaN(n) ? 0 : n;
    }

    function round2(n) {
      return Math.round(n * 100) / 100;
    }

    function format(n, places) {
      return n.toLocaleString("en-US", { minimumFractionDigits: places, maximumFractionDigits: places });
    }

    function money(n) {
      n = round2(n);
      return format(n, n % 1 === 0 ? 0 : 2);
    }

    function isRemoved(el) {
      var box = el.closest("[data-day], .extra-charge");
      var del = box ? box.querySelector('input[name$="-DELETE"]') : null;
      return !!(del && del.checked);
    }

    function setCalc(name, text) {
      form.querySelectorAll('[data-calc="' + name + '"]').forEach(function (el) {
        el.textContent = text;
      });
    }

    /* ---- live price ------------------------------------------------------------------- */
    function recalc() {
      var hectares = 0;
      form.querySelectorAll('input[name^="days-"][name$="-hectares"]').forEach(function (input) {
        if (!isRemoved(input)) hectares += num(input.value);
      });
      var rate = num(rateInput.value);
      var base = Math.round(rate * hectares); // whole denars, like the server
      var extras = 0;
      form.querySelectorAll("[data-extra-amount]").forEach(function (input) {
        if (!isRemoved(input)) extras += num(input.value);
      });
      var total = round2(base + extras);
      setCalc("hectares", format(round2(hectares), 2));
      setCalc("rate", money(rate));
      setCalc("base", money(base));
      setCalc("total", money(total));
      form.dispatchEvent(new CustomEvent("job:total", { detail: { total: total } }));
    }

    /* ---- default rate ---------------------------------------------------------------------- */
    function applyDefaultRate() {
      if (rateTouched) return;
      var rate = null;
      if (specialRate !== null) rate = specialRate;
      else if (rates[operationSelect.value] !== undefined) rate = num(rates[operationSelect.value]);
      if (rate !== null) {
        rateInput.value = rate;
        recalc();
      }
    }

    /* ---- customer → their fields ------------------------------------------------------------- */
    function fieldSelects() {
      return form.querySelectorAll('select[name^="days-"][name$="-farm_fields"]');
    }

    function fieldOption(field) {
      return { value: field.value, text: field.text + (field.hectares ? " (" + field.hectares + " ha)" : "") };
    }

    function loadCustomer(id) {
      specialRate = null;
      if (!id) {
        applyDefaultRate();
        return;
      }
      var url = form.dataset.jobDataUrl.replace("/0/", "/" + id + "/");
      fetch(url, { credentials: "same-origin" })
        .then(function (response) { return response.json(); })
        .then(function (data) {
          specialRate = data.special_rate !== null ? num(data.special_rate) : null;
          var options = data.fields.map(fieldOption);
          fieldSelects().forEach(function (select) {
            avifly.setSelectOptions(select, options, true);
          });
          applyDefaultRate();
        });
    }

    /* ---- multi-day ------------------------------------------------------------------------ */
    function onMultiToggle() {
      var days = form.querySelectorAll("[data-day]").length;
      if (!multiToggle.checked && days > 1) {
        multiToggle.checked = true;
        alert(form.dataset.msgRemoveDays || "Remove the extra days first.");
        return;
      }
      form.classList.toggle("is-multi-day", multiToggle.checked);
    }

    /* ---- quick add dialogs --------------------------------------------------------------------- */
    function showErrors(dialogForm, errors) {
      var box = dialogForm.querySelector("[data-errors]");
      var lines = [];
      Object.keys(errors || {}).forEach(function (key) {
        lines = lines.concat(errors[key]);
      });
      box.textContent = lines.join(" ") || "Something went wrong.";
      box.classList.remove("d-none");
    }

    function addAndSelect(select, option, select_it) {
      if (select.tomselect) {
        select.tomselect.addOption(option);
        if (select_it) select.tomselect.addItem(String(option.value));
      } else {
        var opt = new Option(option.text, option.value, false, select_it);
        select.add(opt);
        if (select_it) {
          opt.selected = true;
          avifly.fire(select, "change");
        }
      }
    }

    function openFieldDialog(button) {
      if (!customerSelect.value) {
        alert(form.dataset.msgPickCustomer || "Choose the customer first.");
        return;
      }
      quickFieldTarget = document.getElementById(button.dataset.quickField);
      var modal = document.getElementById("quick-field");
      bootstrap.Modal.getOrCreateInstance(modal).show();
    }

    document.querySelectorAll("form[data-quick-add]").forEach(function (dialogForm) {
      dialogForm.addEventListener("submit", function (event) {
        event.preventDefault();
        var kind = dialogForm.dataset.quickAdd;
        var url = dialogForm.getAttribute("action");
        if (kind === "field") url = dialogForm.dataset.urlTemplate.replace("/0/", "/" + customerSelect.value + "/");
        var data = {};
        new FormData(dialogForm).forEach(function (value, key) { data[key] = value; });
        avifly.postForm(url, data).then(function (result) {
          if (!result.ok) {
            showErrors(dialogForm, result.data.errors);
            return;
          }
          if (kind === "customer") {
            addAndSelect(customerSelect, { value: String(result.data.value), text: result.data.text }, true);
          } else {
            var option = fieldOption(result.data);
            option.value = String(option.value);
            fieldSelects().forEach(function (select) {
              addAndSelect(select, option, select === quickFieldTarget);
            });
          }
          dialogForm.reset();
          dialogForm.querySelector("[data-errors]").classList.add("d-none");
          bootstrap.Modal.getOrCreateInstance(dialogForm.closest(".modal")).hide();
        });
      });
    });

    /* ---- sections that follow the total (e.g. the payment amount) ------------------------------ */
    function mirrorTotal(total) {
      form.querySelectorAll("[data-follows-total]").forEach(function (box) {
        var scope = box.closest(".card") || form;
        var amount = scope.querySelector("[data-payment-amount]");
        if (!amount) return;
        amount.readOnly = box.checked;
        if (box.checked) amount.value = total;
      });
    }
    form.addEventListener("job:total", function (event) {
      mirrorTotal(event.detail.total);
    });

    /* ---- wiring ------------------------------------------------------------------------------ */
    form.addEventListener("input", function (event) {
      if (event.target === rateInput) rateTouched = true;
      if (event.target.matches('input[name$="-hectares"], [data-extra-amount], #id_job-rate_per_ha')) recalc();
    });
    form.addEventListener("change", function (event) {
      var el = event.target;
      if (el === customerSelect) loadCustomer(customerSelect.value);
      else if (el === operationSelect) applyDefaultRate();
      else if (el === multiToggle) onMultiToggle();
      else if (el.matches("[data-follows-total]")) recalc();
      else if (el.matches('input[name$="-DELETE"]')) {
        var box = el.closest("[data-day], .extra-charge");
        if (box) box.classList.toggle("opacity-50", el.checked);
        recalc();
      }
    });
    form.addEventListener("click", function (event) {
      var button = event.target.closest("[data-quick-field]");
      if (button) {
        event.preventDefault();
        openFieldDialog(button);
      }
    });

    if (!rateTouched && customerSelect.value) loadCustomer(customerSelect.value);
    else applyDefaultRate();
    recalc();
  });
})();
