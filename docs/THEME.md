# SMBFlow Design System & Theme Specification

> **Single Source of Truth for SMBFlow UI/UX Design System**  
> Authoritative reference for visual styling, tokens, color palettes, typography, components, layouts, and states across all frontend pages.

---

## 1. Brand Identity & Principles

- **Product Name**: SMBFlow
- **Brand Essence**: High-performance, enterprise AI orchestration and workflow automation platform for small and medium businesses.
- **Design Philosophy**: Modern, dense, highly scannable, dark-mode native with glassmorphism accents, neon edge glows, and micro-animations.

---

## 2. Color Palette & Design Tokens

Defined in `frontend/tailwind.config.js` and `frontend/src/index.css`:

### Primary Brand Colors
| Token | Hex / RGB | Description |
| :--- | :--- | :--- |
| **Primary (DEFAULT)** | `#6C63FF` (`rgb(108 99 255)`) | Core brand purple-indigo |
| **Primary Light** | `#8379FF` (`rgb(131 121 255)`) | Primary hover / active glow |
| **Accent (DEFAULT)** | `#00D4FF` (`rgb(0 212 255)`) | Cyan highlight & electric accent |
| **Success (DEFAULT)** | `#10E580` (`rgb(16 229 128)`) | Connected status, healthy metrics |
| **Warning (DEFAULT)** | `#FFB800` (`rgb(255 184 0)`) | Attention, re-auth, HITL review |
| **Danger (DEFAULT)** | `#FF4757` (`rgb(255 71 87)`) | Disconnect, errors, critical alerts |

### Dark Mode Semantic Surfaces (`.dark` / default)
| Token | CSS Variable / RGB | Usage |
| :--- | :--- | :--- |
| `surface.base` | `rgb(8 11 20)` | Deep page background |
| `surface.DEFAULT` | `rgb(12 16 26)` | Navigation bars and side panels |
| `surface.elevated`| `rgb(16 22 36)` | Elevated panels, active items |
| `surface.card` | `rgb(18 25 44)` | Integration cards, workflow tiles |
| `surface.hover`| `rgb(24 33 58)` | Interactive hover background |
| `surface.input`| `rgb(12 16 26)` | Inputs, selects, and textareas |

### Borders & Dividers
| Token | RGB | Usage |
| :--- | :--- | :--- |
| `border.DEFAULT` | `rgb(28 40 70)` | Standard card and section borders |
| `border.subtle` | `rgb(20 28 52)` | Internal table and row dividers |

### Typography & Text Hierarchy
| Token | RGB | Usage |
| :--- | :--- | :--- |
| `content.primary` | `rgb(241 245 249)` | Headings, primary labels, account IDs |
| `content.secondary` | `rgb(148 163 184)` | Descriptions, secondary stats |
| `content.muted` | `rgb(71 85 105)` | Placeholders, timestamps, subtle meta |

---

## 3. Typography

- **Sans Family**: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- **Monospace Family**: `'JetBrains Mono', 'Fira Code', monospace` (for latencies, IDs, tokens, code)
- **Headings**:
  - `H1`: `text-2xl font-bold tracking-tight text-content-primary`
  - `H2`: `text-xl font-semibold tracking-tight text-content-primary`
  - `H3`: `text-base font-semibold text-content-primary`
  - `H4`: `text-xs font-bold text-content-secondary uppercase tracking-wider`
- **Body**:
  - Regular: `text-sm text-content-secondary leading-relaxed`
  - Small: `text-xs text-content-secondary`
  - Meta/Tag: `text-[10px] or text-[11px]`

---

## 4. Components & Patterns

### 1. Integration / Marketplace Card
```jsx
<div className="bg-surface-card border border-border rounded-2xl p-6 hover:border-primary/50 transition-all">
  {/* Header with ToolLogo, Display Name, Scope Pill, Status Badge */}
  {/* Description */}
  {/* Account Identity if Connected */}
  {/* Capabilities summary & tags */}
  {/* Action Footer */}
</div>
```

### 2. Status Badges
- **Connected**: `bg-emerald-500/10 text-emerald-400 border border-emerald-500/30` with a pulsing dot.
- **Available / Not Connected**: `bg-surface-hover text-content-muted border border-border`.
- **Reauth Required**: `bg-amber-500/10 text-amber-400 border border-amber-500/30`.
- **Attention / Error**: `bg-rose-500/10 text-rose-400 border border-rose-500/30`.

### 3. Primary Buttons
```jsx
<button className="px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-600 text-xs font-semibold text-white shadow-lg shadow-primary/20 transition">
  Connect with OAuth
</button>
```

### 4. Secondary / Ghost Buttons
```jsx
<button className="px-3 py-2 rounded-xl bg-surface-hover hover:bg-surface-elevated text-xs font-medium text-content-primary border border-border transition">
  Test Connection
</button>
```

### 5. Modals & Drawers
- **Backdrop**: `fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-in fade-in`
- **Modal Container**: `bg-surface-card border border-border rounded-2xl shadow-2xl p-6`
- **Right Drawer**: `bg-surface-card border-l border-border h-full max-w-xl p-6 shadow-2xl overflow-y-auto`

---

## 5. Layout Structure

- **Page Container**: `min-h-screen bg-surface-base text-content-primary p-6 md:p-10`
- **Content Max Width**: `max-w-7xl mx-auto space-y-8`
- **Header Section**: Flex row on `md`, avatar/icon gradient, title, subtitle, quick stats pill, refresh button.
- **Filter Bar**: Flex row with Search input (`max-w-md`), segmented tab pills (`All`, `Connected`, `Available`), category dropdown.
- **Responsive Grid**: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6`

---

## 6. Interactive States

| State | Treatment |
| :--- | :--- |
| **Loading** | Animated skeleton pulse cards with `bg-surface-hover` placeholders. |
| **Error (API Failure)** | Amber/Rose alert banner with descriptive message and `[Retry]` button. (Never "No Integrations Found"). |
| **Empty Results** | Center aligned card with icon, "No Integrations Found", and query clarification text. |
| **Active Testing** | Spinning `Activity` indicator with "Testing..." label, followed by badge showing measured latency in ms. |

---

## 7. Dot-Grid Background Component

The `DotGridBackground` component (`frontend/src/components/common/DotGridBackground.jsx`) provides a subtle, CSS-driven dotted grid for technical and workflow surfaces.

### Approved Usage Areas:
- Integration Marketplace header / hero zone
- Workflow canvas & DAG builder surfaces
- Workflow execution and live log views
- AI Assistant empty state backdrop

### Explicit Exclusions:
- Do **NOT** use behind dense data tables
- Do **NOT** use inside every modal or form
- Do **NOT** use on small cards or notification popovers

### Example:
```jsx
import DotGridBackground from '../components/common/DotGridBackground'

<DotGridBackground className="p-6 rounded-2xl bg-surface-card border border-border">
  <HeaderContent />
</DotGridBackground>
```

