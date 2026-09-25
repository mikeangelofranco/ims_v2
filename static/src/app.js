import Alpine from "@alpinejs/csp";
import htmx from "htmx.org";
import {
  Save,
  Boxes,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Download,
  Plus,
  Pencil,
  EllipsisVertical,
  ArrowLeft,
  ArrowLeftRight,
  ArrowRight,
  Archive,
  BadgeDollarSign,
  BatteryCharging,
  BookOpen,
  Box,
  Bell,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  Check,
  ChartNoAxesColumnIncreasing,
  ChartNoAxesCombined,
  ChartPie,
  ChevronDown,
  ChevronRight,
  CircleCheck,
  CircleHelp,
  CircleX,
  CloudUpload,
  Copy,
  Database,
  Ellipsis,
  Eye,
  EyeOff,
  FileText,
  Folder,
  Funnel,
  Flag,
  Globe2,
  Grid2X2,
  History,
  Headphones,
  House,
  Image,
  Info,
  Link,
  LockKeyhole,
  LogOut,
  Mail,
  Menu,
  MapPin,
  Palette,
  PackageCheck,
  PackageMinus,
  PackageOpen,
  PackagePlus,
  Printer,
  Plug,
  Shield,
  ShieldCheck,
  Search,
  Settings,
  ShoppingCart,
  Sparkles,
  Store,
  Tag,
  TriangleAlert,
  Upload,
  UserPlus,
  Users,
  UsersRound,
  UserRound,
  WalletCards,
  Wifi,
  X,
  Zap,
  createIcons,
} from "lucide";

window.Alpine = Alpine;
window.htmx = htmx;

Alpine.data("mobileMenu", () => ({
  open: false,
  mobile: window.matchMedia("(max-width: 899px)").matches,
  init() {
    this.media = window.matchMedia("(max-width: 899px)");
    this.mediaListener = event => { this.mobile = event.matches; };
    this.media.addEventListener("change", this.mediaListener);
  },
  destroy() {
    this.media.removeEventListener("change", this.mediaListener);
  },
  get sidebarHidden() {
    return this.mobile && !this.open;
  },
  toggle() {
    this.open = !this.open;
  },
}));

Alpine.data("passwordVisibility", () => ({
  visible: false,
  toggle() {
    this.visible = !this.visible;
    const input = this.$root.querySelector('input[name="password"]');
    if (input) input.type = this.visible ? "text" : "password";
  },
}));

Alpine.start();

function syncResponsivePlaceholders() {
  const isMobile = window.matchMedia("(max-width: 767px)").matches;
  document.querySelectorAll("[data-mobile-placeholder]").forEach((input) => {
    input.dataset.desktopPlaceholder ||= input.placeholder;
    input.placeholder = isMobile ? input.dataset.mobilePlaceholder : input.dataset.desktopPlaceholder;
  });
}

syncResponsivePlaceholders();
window.addEventListener("resize", syncResponsivePlaceholders);

const iconSet = {
  Save,
  Boxes,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Download,
  Plus,
  Pencil,
  EllipsisVertical,
  ArrowLeft,
  ArrowLeftRight,
  ArrowRight,
  Archive,
  BadgeDollarSign,
  BatteryCharging,
  BookOpen,
  Box,
  Bell,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  Check,
  ChartNoAxesColumnIncreasing,
  ChartNoAxesCombined,
  ChartPie,
  ChevronDown,
  ChevronRight,
  CircleCheck,
  CircleHelp,
  CircleX,
  CloudUpload,
  Copy,
  Database,
  Ellipsis,
  Eye,
  EyeOff,
  FileText,
  Folder,
  Funnel,
  Flag,
  Globe2,
  Grid2X2,
  History,
  Headphones,
  House,
  Image,
  Info,
  Link,
  LockKeyhole,
  LogOut,
  Mail,
  Menu,
  MapPin,
  Palette,
  PackageCheck,
  PackageMinus,
  PackageOpen,
  PackagePlus,
  Printer,
  Plug,
  Shield,
  ShieldCheck,
  Search,
  Settings,
  ShoppingCart,
  Sparkles,
  Store,
  Tag,
  TriangleAlert,
  Upload,
  UserPlus,
  Users,
  UsersRound,
  UserRound,
  WalletCards,
  Wifi,
  X,
  Zap,
};

createIcons({ icons: iconSet });

function initWorkspaceForm() {
  const form = document.querySelector("[data-workspace-form]");
  if (!form) return;

  const nameInput = form.querySelector("[data-workspace-name]");
  const slugInput = form.querySelector("[data-workspace-slug]");
  const logoInput = form.querySelector('input[name="logo"]');
  const initials = form.querySelectorAll("[data-logo-initials]");
  const logoPreviews = form.querySelectorAll("[data-logo-preview]");
  const namePreviews = form.querySelectorAll("[data-workspace-name-preview]");

  const syncName = () => {
    const name = nameInput.value.trim();
    const letters = name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join("") || "WS";
    initials.forEach((element) => { element.textContent = letters; });
    namePreviews.forEach((element) => {
      element.textContent = name || "Your Workspace";
    });
  };

  const syncSlug = () => {
    const slug = slugInput.value.trim().toLowerCase() || "your-workspace";
    form.querySelectorAll("[data-slug-preview]").forEach((element) => {
      element.textContent = slug;
    });
  };

  nameInput.addEventListener("input", syncName);
  slugInput.addEventListener("input", syncSlug);
  logoInput.addEventListener("change", () => {
    const file = logoInput.files[0];
    if (!file) return;
    const imageUrl = URL.createObjectURL(file);
    logoPreviews.forEach((preview) => {
      const image = document.createElement("img");
      image.src = imageUrl;
      image.alt = preview.classList.contains("workspace-logo-preview")
        ? "Selected workspace logo"
        : "";
      preview.replaceChildren(image);
    });
    const action = form.querySelector("[data-logo-action]");
    if (action) action.textContent = "Change logo";
  });
  syncName();
  syncSlug();
}

initWorkspaceForm();

function initBusinessForm() {
  const form = document.querySelector("[data-business-form]");
  if (!form) return;

  const syncText = (selector, target, fallback) => {
    const input = form.querySelector(selector);
    const output = form.querySelector(target);
    if (!input || !output) return;
    const sync = () => {
      output.textContent = input.tagName === "SELECT"
        ? input.options[input.selectedIndex]?.text || fallback
        : input.value.trim() || fallback;
    };
    input.addEventListener(input.tagName === "SELECT" ? "change" : "input", sync);
    sync();
  };

  syncText("[data-business-name]", "[data-business-name-preview]", "Your Business");
  syncText("[data-business-industry]", "[data-business-industry-preview]", "Select your industry");
  syncText("[data-business-size]", "[data-business-size-preview]", "Select your team size");
  syncText("[data-business-currency]", "[data-business-currency-preview]", "Philippine Peso (PHP)");
  syncText("[data-business-timezone]", "[data-business-timezone-preview]", "Asia/Manila (GMT+08:00)");

  const name = form.querySelector("[data-business-name]");
  if (name) {
    const syncInitials = () => {
      const letters = name.value.trim().split(/\s+/).filter(Boolean).slice(0, 2)
        .map((part) => part[0].toUpperCase()).join("") || "CF";
      form.querySelectorAll("[data-business-initials]").forEach((item) => {
        item.textContent = letters;
      });
    };
    name.addEventListener("input", syncInitials);
    syncInitials();
  }
}

initBusinessForm();

document.querySelectorAll("[data-copy-workspace]").forEach((copyWorkspaceButton) => {
  copyWorkspaceButton.addEventListener("click", async () => {
    const input = copyWorkspaceButton.closest("span")?.querySelector("input");
    if (!input) return;
    try {
      await navigator.clipboard.writeText(input.value);
    } catch {
      input.select();
      document.execCommand("copy");
    }
    copyWorkspaceButton.setAttribute("aria-label", "Workspace URL copied");
  });
});
document.body.addEventListener("htmx:afterSwap", () => createIcons({ icons: iconSet }));

function drawInventoryChart(canvas) {
  const bounds = canvas.getBoundingClientRect();
  if (!bounds.width || !bounds.height) {
    return;
  }

  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(bounds.width * ratio);
  canvas.height = Math.round(bounds.height * ratio);

  const context = canvas.getContext("2d");
  context.scale(ratio, ratio);

  const width = bounds.width;
  const height = bounds.height;
  const inset = Math.max(5, width * 0.018);
  const usableWidth = width - inset * 2;
  const baseline = height - 5;
  const values = [0.18, 0.52, 0.4, 0.78, 0.66, 0.62, 0.88];
  const points = values.map((value, index) => ({
    x: inset + (usableWidth * index) / (values.length - 1),
    y: baseline - value * (height - 18),
  }));

  context.clearRect(0, 0, width, height);
  context.strokeStyle = "#E2E8F0";
  context.lineWidth = 1;
  context.beginPath();
  context.moveTo(inset, baseline);
  context.lineTo(width - inset, baseline);
  context.stroke();

  const tracePath = () => {
    context.beginPath();
    context.moveTo(points[0].x, points[0].y);
    for (let index = 0; index < points.length - 1; index += 1) {
      const current = points[index];
      const next = points[index + 1];
      const midpoint = (current.x + next.x) / 2;
      context.bezierCurveTo(midpoint, current.y, midpoint, next.y, next.x, next.y);
    }
  };

  const gradient = context.createLinearGradient(0, 0, 0, baseline);
  gradient.addColorStop(0, "rgb(37 99 235 / 0.17)");
  gradient.addColorStop(1, "rgb(37 99 235 / 0)");
  tracePath();
  context.lineTo(points.at(-1).x, baseline);
  context.lineTo(points[0].x, baseline);
  context.closePath();
  context.fillStyle = gradient;
  context.fill();

  tracePath();
  context.strokeStyle = "#2563EB";
  context.lineWidth = width < 350 ? 1.5 : 2;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.stroke();

  const finalPoint = points.at(-1);
  context.beginPath();
  context.arc(finalPoint.x, finalPoint.y, width < 350 ? 3 : 4, 0, Math.PI * 2);
  context.fillStyle = "#2563EB";
  context.fill();
}

const chart = document.querySelector("[data-inventory-chart]");
if (chart) {
  drawInventoryChart(chart);
  let resizeFrame;
  window.addEventListener("resize", () => {
    window.cancelAnimationFrame(resizeFrame);
    resizeFrame = window.requestAnimationFrame(() => drawInventoryChart(chart));
  });
}

function syncProductSelection() {
  const panel = document.querySelector("#product-list-panel");
  if (!panel) return;
  const boxes = [...panel.querySelectorAll("[data-product-select]")];
  const selected = boxes.filter(box => box.checked);
  const all = panel.querySelector("[data-select-all]");
  if (all) {
    all.checked = boxes.length > 0 && selected.length === boxes.length;
    all.indeterminate = selected.length > 0 && selected.length < boxes.length;
  }
  const status = panel.querySelector("[data-selection-status]");
  status.hidden = !selected.length;
  status.textContent = `${selected.length} products selected. Export downloads this selection.`;
  const link = document.querySelector("[data-product-export]");
  if (link) {
    const url = new URL(link.href);
    url.search = window.location.search;
    url.searchParams.delete("selected");
    selected.forEach(box => url.searchParams.append("selected", box.value));
    link.href = url.toString();
  }
}
document.addEventListener("change", event => {
  if (event.target.matches("[data-select-all]")) {
    document.querySelectorAll("[data-product-select]").forEach(box => { box.checked = event.target.checked; });
    syncProductSelection();
  } else if (event.target.matches("[data-product-select]")) {
    syncProductSelection();
  } else if (event.target.matches("[data-page-size]")) {
    const url = new URL(window.location.href);
    url.searchParams.set("per_page", event.target.value);
    url.searchParams.delete("page");
    window.location.assign(url);
  }
});
document.addEventListener("keydown", event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    const search = document.querySelector(window.matchMedia("(max-width: 899px)").matches
      ? "#mobile-product-search" : "#product-search");
    if (search) { event.preventDefault(); search.focus(); }
  }
});
document.body.addEventListener("htmx:afterSettle", syncProductSelection);
syncProductSelection();

document.addEventListener("click", event => {
  const link = event.target.closest("[data-focus-target]");
  if (!link) return;
  const target = document.getElementById(link.dataset.focusTarget);
  if (target && target.getClientRects().length) {
    event.preventDefault();
    target.focus();
    target.scrollIntoView({ block: "center", behavior: "smooth" });
  }
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    document.querySelectorAll(".ui-dropdown[open], .ui-filter-panel[open]").forEach(menu => {
      menu.open = false;
      menu.querySelector("summary")?.focus();
    });
  }
});

function syncProductEditor() {
  const form = document.querySelector("[data-product-editor]");
  if (!form) return;
  const checkbox = form.querySelector('[name="track_inventory"]');
  const controls = form.querySelector("[data-inventory-controls]");
  controls.hidden = !checkbox.checked;
  controls.querySelectorAll("input, select").forEach(input => {
    // Unit metadata can still be saved when inventory tracking is disabled.
    if (input.name !== "unit_of_measure") input.disabled = !checkbox.checked;
  });
  form.querySelector("[data-inventory-disabled]").hidden = checkbox.checked;
  form.querySelectorAll("[data-character-count]").forEach(counter => {
    const input = document.getElementById(counter.dataset.characterCount);
    counter.textContent = `${input.value.length}/500`;
  });
}
function initializeProductPanels() {
  const form = document.querySelector("[data-product-editor]");
  if (!form) return;
  form.querySelectorAll("[data-editor-panel]").forEach(panel => {
    const hasErrors = panel.dataset.hasErrors === "true" || Boolean(panel.querySelector(".ui-field-error, .ui-field--invalid, [aria-invalid='true']"));
    const expanded = hasErrors || panel.dataset.defaultExpanded === "true";
    panel.dataset.expanded = String(expanded);
    panel.querySelector("[data-editor-panel-toggle]")?.setAttribute("aria-expanded", String(expanded));
  });
}
document.addEventListener("click", event => {
  const toggle = event.target.closest("[data-editor-panel-toggle]");
  if (!toggle || !window.matchMedia("(max-width: 899px)").matches) return;
  const panel = toggle.closest("[data-editor-panel]");
  const expanded = panel.dataset.expanded !== "true";
  panel.dataset.expanded = String(expanded);
  toggle.setAttribute("aria-expanded", String(expanded));
});
document.addEventListener("invalid", event => {
  const panel = event.target.closest("[data-editor-panel]");
  if (!panel) return;
  panel.dataset.expanded = "true";
  panel.querySelector("[data-editor-panel-toggle]")?.setAttribute("aria-expanded", "true");
}, true);
function previewProductImage(input) {
  const upload = input.closest("[data-image-upload]");
  if (!upload || !input.files.length) return;
  const file = input.files[0];
  const output = upload.closest(".ui-upload-field").querySelector("[data-upload-filename]");
  if (file.size > 5 * 1024 * 1024 || !["image/png", "image/jpeg"].includes(file.type)) {
    input.setCustomValidity("Choose a PNG or JPG image up to 5 MB.");
    output.textContent = input.validationMessage;
    upload.classList.add("ui-upload--invalid");
    return;
  }
  input.setCustomValidity("");
  upload.classList.remove("ui-upload--invalid");
  const preview = upload.querySelector("[data-product-image-preview]");
  if (preview.dataset.previewUrl) URL.revokeObjectURL(preview.dataset.previewUrl);
  const url = URL.createObjectURL(file);
  preview.dataset.previewUrl = url;
  const image = document.createElement("img");
  image.src = url;
  image.alt = "Selected product image";
  preview.replaceChildren(image);
  output.textContent = file.name;
}
document.addEventListener("change", event => {
  if (event.target.closest("[data-product-editor]")) {
    syncProductEditor();
    if (event.target.type === "file") previewProductImage(event.target);
  }
});
document.addEventListener("input", event => {
  if (event.target.matches('[data-product-editor] textarea')) syncProductEditor();
});
document.body.addEventListener("htmx:afterSwap", event => {
  if (event.detail.target.id === "workspace-dialog-body") {
    const dialog = document.getElementById("workspace-dialog");
    if (event.detail.target.querySelector("form")) dialog.showModal();
    else dialog.close();
  }
});
document.addEventListener("click", event => {
  if (event.target.closest("[data-close-dialog]")) document.getElementById("workspace-dialog")?.close();
});
document.addEventListener("catalogCreated", () => document.getElementById("workspace-dialog")?.close());
document.addEventListener("submit", event => {
  if (!event.target.matches("[data-product-editor]")) return;
  event.target.querySelectorAll('button[type="submit"]').forEach(button => {
    button.classList.add("is-loading");
    button.setAttribute("aria-disabled", "true");
  });
});
window.addEventListener("pageshow", () => {
  document.querySelectorAll(".is-loading[aria-disabled]").forEach(button => {
    button.classList.remove("is-loading");
    button.removeAttribute("aria-disabled");
  });
});
initializeProductPanels();
syncProductEditor();

document.addEventListener("click", async event => {
  const thumbnail = event.target.closest("[data-gallery-thumb]");
  if (thumbnail) {
    const gallery = thumbnail.closest(".ui-detail-gallery");
    const image = gallery?.querySelector("[data-gallery-main]");
    if (image) {
      image.src = thumbnail.dataset.imageUrl;
      image.alt = thumbnail.dataset.imageAlt;
      gallery.querySelectorAll("[data-gallery-thumb]").forEach(button =>
        button.classList.toggle("is-active", button === thumbnail));
    }
  }
  const copy = event.target.closest("[data-copy-value]");
  if (copy) {
    const detail = copy.closest(".ui-detail-mobile, .ui-detail-desktop");
    const status = detail?.querySelector("[data-copy-status]");
    try {
      await navigator.clipboard.writeText(copy.dataset.copyValue);
      if (status) status.textContent = `${copy.getAttribute("aria-label").replace("Copy", "Copied")} to clipboard`;
    } catch {
      if (status) status.textContent = "Could not copy to clipboard.";
    }
  }
  const toggle = event.target.closest("[data-description-toggle]");
  if (toggle) {
    const description = toggle.closest(".ui-detail-description")?.querySelector("[data-description-text]");
    const expanded = toggle.getAttribute("aria-expanded") !== "true";
    description.classList.toggle("is-collapsed", !expanded);
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.firstChild.textContent = expanded ? "Show less " : "Show more ";
  }
  if (event.target.closest("[data-print-label]")) window.print();
});
document.querySelectorAll("[data-description-toggle]").forEach(toggle => {
  toggle.closest(".ui-detail-description")?.querySelector("[data-description-text]")?.classList.add("is-collapsed");
});
