# CoreFlow design system

The supplied CoreFlow palette is authoritative. Semantic names are encoded in both `tailwind.config.js` and CSS custom properties in `static/src/app.css`. Feature templates must use names such as `bg-brand-primary`, `text-content-primary`, and `border-ui-default`, not arbitrary hex values.

## Component consistency

The interface is built from a single shared component vocabulary. Product features compose shared Django template components and approved variants; they do not create page-specific versions of familiar controls.

The shared layer will cover buttons, form controls, cards, tables, status badges, alerts, tabs, pagination, menus, dialogs, navigation, loading states, and empty states as those elements are introduced. Each component owns its spacing, typography, colors, borders, radius, icon sizing, accessibility behavior, and interaction states.

When an existing component does not fit a requirement, first determine whether the difference expresses a reusable semantic variant. If it does, extend the shared component and document the variant. If it does not, compose existing primitives without changing their established visual language.

Component states must be designed together: default, hover, focus-visible, active, disabled, loading, invalid, and read-only where relevant. Consistency includes behavior and accessibility—not only appearance.

| Role | Value |
| --- | --- |
| Primary / hover / active | `#2563EB` / `#1D4ED8` / `#1E40AF` |
| Success | `#16A34A` |
| Warning | `#F59E0B` |
| Danger | `#DC2626` |
| Info | `#0891B2` |
| Primary / secondary / muted text | `#0F172A` / `#475569` / `#94A3B8` |
| Background / surface | `#F8FAFC` / `#FFFFFF` |
| Default / input / sidebar border | `#E2E8F0` / `#CBD5E1` / `#E5E7EB` |

- Typography: Inter with safe system fallbacks.
- Icons: Lucide.
- Default radius: 12px.
- Shadows: use `shadow-subtle` and `shadow-elevated`.
- Gradients: use `bg-gradient-brand` and `bg-gradient-info`.
- Status labels must use the corresponding semantic color, never color alone; include text or an icon.
