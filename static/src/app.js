import Alpine from "@alpinejs/csp";
import htmx from "htmx.org";
import {
  ArrowRight,
  BookOpen,
  Box,
  BriefcaseBusiness,
  ChartNoAxesColumnIncreasing,
  ChartNoAxesCombined,
  ChartPie,
  ChevronDown,
  ChevronRight,
  CircleCheck,
  Ellipsis,
  Menu,
  Shield,
  ShoppingCart,
  TriangleAlert,
  Users,
  createIcons,
} from "lucide";

window.Alpine = Alpine;
window.htmx = htmx;

Alpine.data("mobileMenu", () => ({
  open: false,
  toggle() {
    this.open = !this.open;
  },
}));

Alpine.start();

createIcons({
  icons: {
    ArrowRight,
    BookOpen,
    Box,
    BriefcaseBusiness,
    ChartNoAxesColumnIncreasing,
    ChartNoAxesCombined,
    ChartPie,
    ChevronDown,
    ChevronRight,
    CircleCheck,
    Ellipsis,
    Menu,
    Shield,
    ShoppingCart,
    TriangleAlert,
    Users,
  },
});

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
