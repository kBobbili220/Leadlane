import { buildServicePayload, createService, formatPrice, listServices } from "./service-client.mjs";

const byId = (id) => document.getElementById(id);
const form = byId("service-form");
// The retained browser screen is a design reference. Owner authentication and
// service management live in the native app; the API rejects anonymous writes.
byId("form-fields").disabled = true;
byId("submit-button").disabled = true;
byId("submit-button").querySelector(".button-label").textContent = "Create services in the mobile app";
byId("open-catalog").hidden = true;
const controls = { name: byId("name"), price: byId("price"), duration: byId("duration"), unit: byId("unit") };
let saving = false;
let catalogLoading = false;
let catalogOffset = 0;
const PAGE_SIZE = 50;

function values() {
  return {
    name: controls.name.value,
    description: byId("description").value,
    pricingMode: form.elements.pricing_mode.value,
    price: controls.price.value,
    duration: controls.duration.value,
    unit: controls.unit.value,
    isActive: byId("is-active").checked,
  };
}

function updatePreview() {
  const input = values();
  const custom = input.pricingMode === "custom";
  controls.price.disabled = custom || saving;
  byId("price-required").hidden = custom;
  byId("custom-price-hint").hidden = !custom;
  controls.price.placeholder = custom ? "Quoted per job" : "150.00";
  byId("preview-name").textContent = input.name.trim() || "Your signature service";
  byId("preview-description").textContent = input.description.trim() || "The details that make your business stand out.";
  byId("preview-status").textContent = input.isActive ? "Available for quotes" : "Saved as inactive";
  byId("preview-from").textContent = custom ? "Made to fit the job" : "Starting at";
  const { payload } = buildServicePayload({ ...input, name: "Preview", duration: "" });
  byId("preview-price").textContent = custom ? "Custom quote" : formatPrice(payload?.base_price_minor ?? 0);
  byId("preview-duration").textContent = /^\d+$/.test(input.duration) && Number(input.duration) > 0
    ? `${Number(input.duration).toLocaleString()} min` : "Flexible duration";
  if (custom) clearFieldError("price");
}

function clearFieldError(key) {
  controls[key]?.removeAttribute("aria-invalid");
  const error = byId(`${key}-error`);
  if (error) { error.hidden = true; error.textContent = ""; }
}

function showFieldErrors(errors) {
  for (const key of Object.keys(controls)) clearFieldError(key);
  for (const [key, message] of Object.entries(errors)) {
    const error = byId(`${key}-error`);
    if (!error) continue;
    error.textContent = message;
    error.hidden = false;
    controls[key]?.setAttribute("aria-invalid", "true");
  }
  controls[Object.keys(errors)[0]]?.focus();
}

function setSaving(value) {
  saving = value;
  byId("form-fields").disabled = value;
  byId("submit-button").disabled = value;
  form.setAttribute("aria-busy", String(value));
  byId("submit-button").querySelector(".button-label").textContent = value ? "Saving your service…" : "Create service";
  byId("submit-button").querySelector(".spinner").hidden = !value;
  byId("submit-button").querySelector(".button-arrow").hidden = value;
  updatePreview();
}

function showSuccess(service) {
  byId("saved-name").textContent = service.name;
  byId("saved-description").textContent = service.description || "";
  byId("saved-description").hidden = !service.description;
  byId("saved-price").textContent = formatPrice(service.base_price_minor);
  byId("saved-duration").textContent = [service.estimated_duration_minutes ? `${service.estimated_duration_minutes} min` : null, `per ${service.unit_label}`].filter(Boolean).join(" · ");
  byId("saved-status").textContent = service.is_active ? "Active" : "Inactive";
  byId("saved-status").classList.toggle("inactive", !service.is_active);
  byId("success-description").textContent = service.is_active
    ? "Added to your catalog and ready for your next quote."
    : "Added to your catalog as inactive. You can make it available when you’re ready.";
  byId("setup-view").hidden = true;
  byId("success-view").hidden = false;
  document.title = "Service saved · Detailflow";
  window.scrollTo({ top: 0, behavior: "auto" });
  byId("success-title").focus({ preventScroll: true });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (byId("form-fields").disabled && !saving) return;
  if (saving) return;
  byId("save-error").hidden = true;
  const { payload, errors } = buildServicePayload(values());
  showFieldErrors(errors);
  if (!payload) return;
  setSaving(true);
  try {
    const service = await createService(payload);
    showSuccess(service);
  } catch (error) {
    showFieldErrors(error.fields || {});
    byId("save-error-title").textContent = error.uncertain ? "Let’s double-check that save." : "Something needs another look.";
    byId("save-error-message").textContent = error.message;
    byId("error-check-catalog").hidden = !error.uncertain;
    byId("save-error").hidden = false;
    byId("save-error").scrollIntoView({ block: "nearest", behavior: "smooth" });
  } finally {
    setSaving(false);
  }
});

form.addEventListener("input", (event) => {
  if (Object.hasOwn(controls, event.target.id)) clearFieldError(event.target.id);
  updatePreview();
});
form.addEventListener("change", updatePreview);

byId("add-another").addEventListener("click", () => {
  form.reset();
  byId("save-error").hidden = true;
  showFieldErrors({});
  byId("success-view").hidden = true;
  byId("setup-view").hidden = false;
  document.title = "Your next service · Detailflow";
  updatePreview();
  window.scrollTo({ top: 0, behavior: "auto" });
  controls.name.focus({ preventScroll: true });
});

function serviceCard(service) {
  // All user-supplied content is inserted as text, never interpreted as HTML.
  const card = document.createElement("article");
  card.className = "catalog-item";
  const head = document.createElement("div");
  head.className = "catalog-item-head";
  const name = document.createElement("h3");
  name.textContent = service.name;
  const status = document.createElement("span");
  status.className = `status-badge${service.is_active ? "" : " inactive"}`;
  status.textContent = service.is_active ? "Active" : "Inactive";
  head.append(name, status);
  card.append(head);
  if (service.description) {
    const description = document.createElement("p");
    description.textContent = service.description;
    card.append(description);
  }
  const price = document.createElement("div");
  price.className = "catalog-item-price";
  price.textContent = formatPrice(service.base_price_minor);
  const detail = document.createElement("small");
  detail.textContent = [service.estimated_duration_minutes ? `${service.estimated_duration_minutes} min` : null, `per ${service.unit_label}`].filter(Boolean).join(" · ");
  price.append(detail);
  card.append(price);
  return card;
}

function catalogMessage(text) {
  const message = document.createElement("p");
  message.className = "catalog-message";
  message.textContent = text;
  return message;
}

async function loadCatalog(reset = false) {
  if (catalogLoading) return;
  catalogLoading = true;
  const content = byId("catalog-content");
  content.setAttribute("aria-busy", "true");
  byId("catalog-more").disabled = true;
  byId("catalog-retry").hidden = true;
  content.querySelector(".catalog-load-error")?.remove();
  if (reset) {
    catalogOffset = 0;
    byId("catalog-more").hidden = true;
    content.replaceChildren(catalogMessage("Loading your services…"));
  }
  try {
    const services = await listServices({ offset: catalogOffset, limit: PAGE_SIZE });
    if (reset) content.replaceChildren();
    for (const service of services) content.append(serviceCard(service));
    catalogOffset += services.length;
    if (catalogOffset === 0) content.append(catalogMessage("Your catalog is a clean slate. Add your first service to get started."));
    byId("catalog-more").hidden = services.length < PAGE_SIZE;
  } catch (error) {
    if (reset) content.replaceChildren();
    // Replace a previous load-more error rather than stacking repeated messages.
    content.querySelector(".catalog-load-error")?.remove();
    const message = catalogMessage(error.message);
    message.classList.add("catalog-load-error");
    content.append(message);
    byId("catalog-retry").hidden = false;
    byId("catalog-more").hidden = true;
  } finally {
    catalogLoading = false;
    content.setAttribute("aria-busy", "false");
    byId("catalog-more").disabled = false;
  }
}

function openCatalog() {
  byId("catalog-dialog").showModal();
  loadCatalog(true);
}
for (const id of ["open-catalog", "success-catalog", "error-check-catalog"]) byId(id).addEventListener("click", openCatalog);
byId("close-catalog").addEventListener("click", () => byId("catalog-dialog").close());
byId("catalog-dialog").addEventListener("click", (event) => {
  const dialog = byId("catalog-dialog");
  const rect = dialog.getBoundingClientRect();
  if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
});
byId("catalog-more").addEventListener("click", () => loadCatalog());
byId("catalog-retry").addEventListener("click", () => loadCatalog(catalogOffset === 0));
updatePreview();
