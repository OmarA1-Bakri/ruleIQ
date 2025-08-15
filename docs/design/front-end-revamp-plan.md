## Executive summary
The current front-end shows strong functional breadth but lacks a cohesive visual system and modern motion/interaction polish. Inconsistent spacing, typographic scale, and component variants reduce clarity and perceived quality. Accessibility is partial; color contrast and focus states require standardization. Performance can be improved for LCP and input responsiveness by optimizing hero media, reducing layout shift, and refining hydration. The revamp will unify brand expression across landing, auth, dashboard, and assessments with a consistent design language, accessible components, and performance budgets. Targets: WCAG 2.2 AA, under 2.5 s LCP on 3G, sub-100 ms interaction latency.

## Holistic front-end audit scope
- Visual identity and branding: color roles, elevation, spacing rhythm, iconography alignment
- Interaction and flows: landing hero clarity, dual CTAs, trust signals; auth friction; assessments progress and autosave
- Components: unify buttons, inputs, cards, banners, toasts, modals with variants and tokens
- Accessibility: landmarks, skip link, focus order, aria labels, error association, contrast verification
- Performance: fonts preconnect and fallback, responsive images, reduced hydration, skeletons, suspense

## Staged improvement plan
- Stage 0 Baselines and tokens: implement design tokens and type ramp; wire theme provider across app
- Stage 1 Landing hero: rebuild hero, trust signals, responsive media; set LCP KPI and CLS budget
- Stage 2 Auth flows: update login and signup with error handling and SSO affordances
- Stage 3 Dashboard and widgets: restructure shell; widget grid with suspense and skeletons
- Stage 4 Assessments flow: progress rail, card layout, sticky actions; keyboard-first controls
- Stage 5 A11y and Performance pass: Lighthouse CI budgets, axe checks, keyboard testing
- Stage 6 Handover: style guide, examples, contribution rules, commit scopes

## Risks and dependencies
- Token rollout may cause regressions; use phased adoption and visual diffing
- Hero media may require CDN and responsive art direction
- SSO visual parity depends on provider configuration and copy alignment


## Audit log: Landing page (frontend/app/(public))

Checklist
- [ ] Visual identity: consistent color roles, spacing rhythm, iconography alignment
- [ ] Typography: apply defined type ramp; check headings hierarchy and line-length
- [ ] Layout: hero grid responsive at 320, 768, 1024, 1280; safe areas respected
- [ ] CTAs: primary/secondary contrast, hit area ≥44x44, clear affordances
- [ ] Trust signals: logo row responsive, alt text present
- [ ] Accessibility: landmarks, skip link, focus order, visible focus ring, aria-labels
- [ ] Performance: LCP image optimized, width/height set, priority, preload as needed; CLS ≤0.1
- [ ] Motion: prefers-reduced-motion respects; non-blocking decorative animations

Metrics to capture
- LCP (3G): target ≤2.5s
- CLS: target ≤0.1
- INP: target <100ms
- Lighthouse a11y score: ≥95

Initial findings
- Pending: locate landing route within frontend/app/(public) and enumerate hero components, media assets, and section structure.
- Action: identify LCP candidate image/video, measure current LCP and CLS, verify font loading strategy (preconnect, display), and check focus visibility.

Planned fixes (landing hero)
- Replace hero media with responsive sources and explicit dimensions; set priority for LCP asset.
- Normalize spacing and type scale to style guide snippet; unify CTA variants.
- Add skip link and ensure header/main landmarks; confirm visible keyboard focus.
- Preconnect fonts and adjust font-display to optional; ensure fallback stack with minimal layout shift.


## Detailed audit findings — Marketing landing (frontend/app/marketing/page.tsx)

Scope
- File: frontend/app/marketing/page.tsx
- Key libs: framer-motion (motion), next/image (Image), lucide-react icons
- Custom components: Button, Card, Input, TextEffect, TypewriterEffect, InfiniteSlider, SparklesBackground, GradientBackground, AnimatedGrid, FloatingElements, ShimmerButton, EnhancedMetricCard, NumberTicker

Structure inventory
- Hero section: full-viewport h-screen with gradient background; animated eyebrow; TextEffect H1; motion paragraph; TypewriterEffect; primary ShimmerButton CTA and secondary outline Button; animated compliance badges; no explicit hero media in hero (LCP candidate likely later Image)
- Social proof: GradientBackground container with InfiniteSlider of client logos (placeholder SVGs)
- Metrics: EnhancedMetricCard x4 with icon and optional change trend
- Features: 3 Cards with icons and copy; motion viewport animations
- Product demo: large next/Image (1200×800 placeholder) likely the LCP element
- How it works: motion H1 and 3 Cards (connect systems, analyze, insights)
- Testimonials: GradientBackground cards with avatar Image
- CTA: email Input and ShimmerButton
- Footer: 4 columns + copyright; anchor links to in-page sections

Accessibility review
- Landmarks: top-level is a div; sections use <section> and <footer> which provide landmarks; consider wrapping page in <main> to provide explicit main landmark
- Headings: H1 appears under motion.h1 for "Simple Steps to Full Compliance" but hero uses TextEffect for the main message; ensure a semantic H1 exists for the hero; currently hero uses TextEffect with class text-5xl and may not emit an h1 tag
- Focus states: Button variants likely style focus, but verify visible focus outline on ShimmerButton and outline Button; ensure keyboard tab order places skip link before header content
- Forms: CTA email Input has placeholder but no label; add aria-label or visible label and describedby hint
- Animation and motion: frequent motion.div animations; ensure prefers-reduced-motion queries disable/soften; InfiniteSlider should pause for reduced-motion; ShimmerButton has repeating arrow animation — should be reduced-motion aware
- Images: next/Image used; testimonials avatars have alt names OK; product demo alt is generic "Product demo" — improve descriptive alt; trust logos in slider use placeholder images — ensure alt text indicates brand name when real assets replace placeholders
- Links: Footer anchors point to section IDs; verify target sections exist (#pricing, #integrations, #demo may not exist on this page)

Performance review
- LCP candidate: demo Image at 1200×800 with rounded-2xl and shadow; likely below hero fold in some viewports; hero lacks LCP media, so headline text or later image may be LCP. For consistency, place a hero foreground LCP media or ensure earliest meaningful content is fast
- next/Image: width/height provided — good for CLS; consider priority for first meaningful image; supply sizes attr for responsive breakpoints; ensure appropriate quality and format (WebP/AVIF) when real assets used
- Fonts: no explicit next/font usage in this file; verify global setup uses preconnect and display strategy to minimize FOIT/FOUT
- Animations: motion effects on many elements — ensure they do not cause layout thrash; prefer transform/opacity
- InfiniteSlider: continuous animation can be costly on low-end devices; consider reducing FPS or pausing when offscreen
- Metric Cards: use skeletons only where async data loads; currently static numbers; OK
- Bundling: imports multiple custom components; verify tree-shaking and avoid heavy client hooks in server-rendered sections

Design and content review
- Type scale: hero uses text-5xl md:7xl lg:8xl — check against style guide ramp
- Color roles: uses teal-600, gradients; ensure alignment with tokenized roles and contrast AA; buttons: outline button border-teal-600 on white — verify contrast
- Spacing: consistent py-20 blocks; h-screen hero may cause mobile viewport issues with dynamic toolbar; consider min-h-dvh and content-safe padding
- CTAs: primary "Start Free Trial" and secondary "Watch 2-min Demo"; add aria-labels for screen readers; ensure hit area ≥44px
- Copy: clear value prop; typewriter adds context "For UK SMBs / AI-Powered / Stay Compliant"

Actionable changes (code-level)
- Semantics: wrap page content in <main id="main"> ... </main>; add <a href="#main" className="sr-only focus:not-sr-only ...">Skip to content</a> near top
- Headings: ensure exactly one h1 in hero; change TextEffect wrapper to render an h1 or place within <h1></h1>
- Forms: add label for email input; e.g., visually-hidden label with id linked via aria-describedby; validate input type and error messaging
- Motion: add reduced-motion guard to framer variants; disable InfiniteSlider animation when reduced-motion; reduce shimmer arrow animation under reduced-motion
- LCP: if product demo stays primary LCP, mark it priority and preload; else introduce a hero image/illustration and make it the LCP with explicit sizes and priority
- Images: add sizes="(max-width: 768px) 100vw, 1200px" on large Image; confirm loading="lazy" for non-critical images
- Footer links: ensure in-page ids (#pricing, #integrations, #demo) exist or route to /pricing etc.

Proposed tasks (granular)
- a11y(landing): add main landmark, skip link, and semantic h1 in hero
- a11y(landing): label email input and add helper text; keyboard focus visible on all CTAs
- perf(landing): set LCP image strategy with next/Image priority and sizes; preload hero font if used
- perf(landing): add prefers-reduced-motion handling; pause InfiniteSlider offscreen and when reduced
- ui(tokens): replace hard-coded teal classes with semantic tokens; align typography to type ramp
- content(landing): refine alt texts; ensure trust badges accessible and not purely animated
- layout(landing): replace h-screen with min-h-dvh and safe-area padding; verify 320/768/1024/1280 grids
- qa(metrics): measure and record Lighthouse (mobile 3G): LCP, CLS, INP; attach screenshots to PR

Next steps
- Implement semantic fixes and LCP strategy in marketing page
- Measure baseline and updated metrics; log in this plan
- Proceed to audit frontend/app/(public) after applying learning from marketing page
