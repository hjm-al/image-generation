# Art Direction and Style Prompting

Use this reference when visual style is central to the deliverable, when the brief uses a vague or overloaded style label, or when an edit must preserve content while changing its visual treatment.

Style is not a pile of adjectives. Treat it as a controlled visual system that another person can verify in the finished image.

## Separate Content From Style

For a new image, describe the content first and the style second. The model should know what it is depicting before it decides how to depict it.

- **Content contract:** subject, quantity, action, identity, materials, setting, text, and required relationships.
- **Style contract:** medium, edge behavior, rendering, surface, palette, light, camera, composition, and graphic system.

For image-to-image work, state two explicit contracts:

```text
Preserve: subject identity, count, pose, silhouette, product geometry, camera, crop, layout anchors, readable text, and scene relationships.
Restyle: medium, line or edge treatment, shading model, surface texture, palette, lighting treatment, and optional graphic overlays.
```

Treat anything not listed as changeable as preserved. "Preserve the layout" is too broad if the face, logo, or interface grid can still move.

## Build A Style Stack

Define these layers in order. Omit a layer only when it does not affect the result.

| Layer | What to specify | Observable prompt language |
|---|---|---|
| Medium | One primary production method | "gouache illustration", "editorial photograph", "cel-shaded animation still" |
| Edge and shape | Contour, geometry, simplification | "uneven waxy outlines", "crisp hard-edged planes", "rounded silhouettes" |
| Shading and volume | How depth is built | "two shadow bands", "flat fills", "soft contact shadows", "crosshatching" |
| Surface and mark-making | Material evidence | "visible paper grain", "dry-brush gaps", "porcelain reflections", "halftone dots" |
| Palette and value | Color strategy and tonal range | "four spot inks on off-white", "high-key neutrals with one red accent" |
| Light and camera | Source, direction, optics, contrast | "side light, 50 mm, shallow depth of field", "diffuse overhead light, no lens blur" |
| Composition and graphic system | Layout, hierarchy, typography, UI | "centered portrait with quiet lower third", "12-column grid with compact captions" |
| Anti-drift | The properties that must not appear | "no photorealistic shading", "no extra panels", "no ornate borders" |

Use one primary medium. Add at most one supporting graphic system, and state which one dominates. A coherent blend often looks like "80 percent editorial photograph, with a restrained 20 percent Swiss typographic grid over it."

## Core Style Families

These are starting points, not preset prompt strings. Convert the chosen family into the style stack and then describe the actual subject.

### Photographic Directions

| Direction | Add these observable controls |
|---|---|
| Editorial or fashion photograph | Art-directed set, styling, precise crop, controlled fabric behavior, believable skin texture, deliberate highlight shape |
| Documentary or street photograph | Available light, candid timing, uneven framing, modest depth of field, restrained retouching, plausible motion |
| Cinematic still | Named shot size and lens feel, motivated key light, set depth, atmospheric separation, specific contrast and color grade |
| Studio product photograph | Background sweep or set, surface finish, reflection shape, contact shadow, camera height, focal length, clean edge control |
| Analog film photograph | Stock-like grain, halation, limited dynamic range, slight color crossover, practical imperfections, consistent exposure |
| Monochrome photograph | Tonal separation, highlight retention, grain scale, contrast curve, no accidental spot-color unless requested |
| Macro or technical photograph | Working distance, plane of focus, scale cue, controlled reflections, shallow or stacked depth of field |

"Cinematic" alone is underspecified. Say what creates the cinematic effect: lens, framing, contrast, production design, light motivation, or atmosphere.

### Illustration Directions

| Direction | Add these observable controls |
|---|---|
| Cel-shaded anime or animation still | Line weight, flat fill count, hard shadow shapes, highlight placement, expression rules, background detail level |
| Comic, manga, or ink illustration | Panel logic, contour weight, hatching direction, black balance, halftone behavior, speech-space policy |
| Painterly illustration | Brush direction, edge lost-and-found, paint opacity, canvas tooth, value grouping, palette knife or impasto behavior |
| Watercolor or gouache | Pigment pooling, granulation, dry-brush gaps, paper show-through, transparent glazes or opaque layers, restrained edge control |
| Crayon, colored pencil, or marker | Waxy or fibrous strokes, pressure variation, uneven fill, visible overlap, limited blending, clean-paper boundaries |
| Vector or flat illustration | Geometric simplification, uniform or tapered contours, solid color regions, icon-like shapes, controlled detail count |
| Children's book illustration | Simplified anatomy, readable silhouettes, expressive faces, friendly proportions, hand-made texture, age-appropriate complexity |
| Storyboard or concept frame | Clear staging, camera arrows or panels only if required, value-first rendering, readable action, restrained surface detail |

For anime and comic work, define the rendering system instead of naming a franchise. State line behavior, shadow count, eye treatment, anatomy stylization, and background finish.

### Print, Poster, And Graphic Directions

| Direction | Add these observable controls |
|---|---|
| Swiss or international editorial layout | Grid, asymmetric balance, typographic hierarchy, generous whitespace, limited palette, functional alignment |
| Screen print | Limited spot inks, bold separations, slight registration offset, visible mesh or ink edges, no continuous-tone gloss |
| Risograph | Two to four spot inks, grain, uneven coverage, misregistration, overprint behavior, uncoated paper feel |
| Vintage travel poster | Flat color masses, simplified landmarks, strong silhouettes, period-neutral typography policy, restrained print texture |
| Collage or zine | Cut edges, torn fibers, visible paste-up layers, mixed source texture, deliberate scale shifts, controlled chaos |
| Infographic poster | Information hierarchy, numbered modules, consistent icon language, chart geometry, readable labels, reserved text areas |
| UI, HUD, or game interface | Panel hierarchy, icon family, state indicators, spacing system, edge treatment, safe zones, contrast under the game image |
| Pixel art | Base pixel grid, palette limit, dithering rule, outline policy, animation-ready silhouette, no filtered anti-aliasing |

When typography is not the primary deliverable, reserve space and add text in post-production. Image models often produce plausible-looking but incorrect lettering.

### Three-Dimensional And Technical Directions

| Direction | Add these observable controls |
|---|---|
| Stylized clay or vinyl render | Simplified geometry, matte subsurface feel, soft occlusion, rounded edges, small imperfection set, studio background |
| Product visualization | Accurate proportions, material separation, controlled reflections, realistic bevels, studio lighting, clean contact shadows |
| Isometric technical illustration | Fixed axonometric angle, line hierarchy, cutaway logic, labels and leader lines, consistent scale, white or grid background |
| Low-poly render | Visible planar facets, constrained palette, flat or softly shaded faces, deliberate silhouette simplification |
| Exploded-view render | Component separation along a readable axis, consistent perspective, connector or fastener logic, restrained annotation space |

## Mixed Styles

Use a mixed style only when each system has a job.

1. Choose the primary medium that controls most of the frame.
2. Assign one supporting system to a bounded element, such as labels, borders, UI, or background texture.
3. State the ratio or hierarchy.
4. Add anti-drift constraints for both systems.

Useful combinations include:

- realistic product photography with a clean technical annotation layer;
- painterly environment with flat vector signage;
- cel-shaded characters with a restrained photographic background;
- clay-rendered objects with hand-drawn arrows and labels;
- documentary photography with a controlled editorial grid.

Avoid combining mutually exclusive rendering logics without assigning roles, such as "photorealistic, watercolor, anime, oil painting, and 3D." That usually produces a blended surface with no stable visual grammar.

## Replace Vague Style Words

Convert taste words into properties that can be checked:

| Vague word | Replace with |
|---|---|
| Premium | Specific materials and finishes, restrained palette, controlled reflections, precise edges, generous spacing |
| Cinematic | Shot size, lens behavior, motivated lighting, production design, atmospheric depth, contrast curve |
| Vintage | Production process, print artifacts, period-specific palette, typography policy, wear pattern, date window |
| Artistic | Medium, abstraction level, mark-making, edge behavior, composition rule, intentional distortion |
| Cute | Proportion changes, rounded shapes, expression vocabulary, softer value contrast, detail density |
| Epic | Scale cues, low or high viewpoint, layered depth, atmospheric perspective, small figures against large forms |
| Minimal | Few elements, strong whitespace, limited palette, reduced detail, one clear focal hierarchy |
| Hand-drawn | Uneven contour, pressure variation, visible tool texture, imperfect fills, controlled wobble |
| Photorealistic | Plausible optics, skin or material texture, contact shadows, highlight behavior, restrained stylization |
| Futuristic | Specific materials, interfaces, silhouettes, lighting technology, product language, social or spatial context |

## Artist And Franchise References

Prefer visual properties over names of living artists. "In the style of [artist]" is inconsistent across models, can collapse several unrelated works into one shorthand, and raises avoidable copying and publicity concerns.

Translate the intended reference into:

- medium and tool behavior;
- edge and shape language;
- palette and value structure;
- lighting and camera;
- composition and graphic system;
- level of realism or abstraction.

Do the same for characters and franchises. Describe an archetype, silhouette, material system, or design grammar instead of relying on a protected character name. Preserve user-supplied identity references only when the user has the right to use them.

## Prompt Block

Use this block after the content description:

```text
Art direction:
Primary medium: [one medium]
Supporting visual system: [optional bounded system and hierarchy]
Edges and shapes: [contour, geometry, simplification]
Rendering and surface: [shading model, texture, material evidence]
Palette and values: [dominant colors, accents, tonal range]
Light and camera: [direction, hardness, lens, depth, contrast]
Composition and graphics: [framing, layout, icon or type policy]
Avoid style drift: [accidental photorealism, extra panels, gradients, lettering, borders, or other unwanted properties]
Preserve: [edit only: identity, geometry, layout, and other locked content]
```

Keep the block proportional to the task. A simple portrait does not need every layer; a multi-panel poster or image-to-image restyle usually does.

## Review Style Results

Judge the intended style contract before revising the prompt.

- `C7`: the result mixes incompatible media, loses the primary medium, or uses the wrong style for the deliverable.
- `C8`: light, value structure, palette, or color grade contradicts the contract.
- `C5`: style overlays overwhelm the subject, change the crop, or break the graphic hierarchy.
- `C4`: the style introduces unintended lettering, signatures, logos, or watermarks.
- Preservation failures may instead be `C1`, `C3`, or `C5` when identity, culture/material, or layout changes.

Record which clause failed. For example, "canvas texture became smooth 3D plastic" points to the medium and surface clauses; "the poster grid pushed the product out of frame" points to composition.

If a style result fails, change the smallest relevant layer:

1. medium or supporting system;
2. edges and shape;
3. shading and surface;
4. palette and light;
5. composition and graphics;
6. anti-drift constraints.

Do not append more style adjectives. Add one observable property or remove one conflicting system, then use the review and versioning rules in [quality-loop.md](quality-loop.md).

## Source Boundary

This guide is an independent synthesis of general art-direction practice and structural patterns reviewed in OpenDesign's image prompt catalog. It does not reproduce upstream prompt text or preview images. See [../ATTRIBUTIONS.md](../ATTRIBUTIONS.md) for the exact reviewed revision and the mixed-license source boundary.
