# Image Prompt Guide

Use this guide when the visual brief is vague, when a prompt will be reused, or when a result needs a disciplined revision.

## Prompt Shape

Write the prompt in this order:

```text
Use case: [deliverable and audience]
Asset type: [orientation and image category]
Primary request: [subject, quantity, action, and mandatory details]
Scene: [location, time, weather, background, environment]
Subject details: [materials, structure, texture, contact points, required anatomy]
Composition: [shot size, placement, sight line, aspect ratio, negative space]
Style and medium: [one dominant visual language]
Lighting and mood: [direction, contrast, atmosphere]
Color palette: [dominant colors, accents, colors to avoid]
Text and layout: [reserved space or exact short text policy]
Constraints: [unwanted text, logos, watermarks, duplication, anatomy, borders]
```

The exact labels are optional. The information order is what keeps a model from solving style before it understands the subject.

## Replace Adjectives With Observable Evidence

Turn subjective words into properties that a reviewer can point to in the finished image:

- "premium" -> material, finish, edge treatment, lighting, and production quality;
- "natural" -> skin texture, uneven fibers, realistic contact shadows, and restrained retouching;
- "cinematic" -> lens, framing, light direction, contrast, and atmosphere;
- "clean" -> controlled background, spacing, alignment, and limited palette.

Prefer statements such as "visible woven straw fibers, tied joints, and a wooden handle" over "authentic traditional craft". If a detail matters, state where it appears and what it connects to.

## Art Direction And Style

Treat style as a visual system rather than a list of adjectives. Define the primary medium, edge and shape language, shading or rendering model, surface texture, palette and values, light and camera, and any supporting graphic system.

Use one dominant medium and at most one supporting graphic system. For edits, separate the preservation contract from the restyling contract so identity, geometry, crop, layout, and readable text do not drift while the treatment changes.

When the style is central, hybrid, ambiguous, or expressed through a named artist or franchise, read [art-directions.md](art-directions.md). It provides style families, a reusable style stack, observable replacements for vague words, and review guidance.

## Cultural And Functional Objects

For a cultural, historical, or functional object:

- name the real material and construction;
- describe what the object is used for and how the visible parts connect;
- state what it must not become when visual confusion is likely, such as "a woven prop, not a fantasy creature" or "a lacquered wood utensil, not molded plastic";
- avoid unsupported period, region, or ritual claims when the brief does not establish them.

Negative constraints should disambiguate the subject, not carry the entire description.

## Text And Typography

Image models are unreliable at exact typography. Unless exact lettering is the primary task:

- reserve clear negative space for later typesetting;
- describe where that space sits and roughly how much of the frame it occupies;
- state "no text, no letters, no logo, no watermark";
- keep required text short and provide an exact spelling list;
- inspect letter-by-letter after generation.

## Keep Variables Separate

Store the stable brief separately from experiment controls:

- **brief**: purpose, subject, scene, composition, text policy, constraints;
- **request controls**: model, `n`, size, quality, output format, response format;
- **editable clauses**: the smallest prompt sections being tested.

For a model comparison, keep the prompt, `n`, size, quality, and output format fixed. Change only the model. Do not infer that a model is missing from a single 502, and treat a group-specific 404 as an access result until the exact model ID and entitlement are confirmed.

## Iteration Discipline

Change one group of variables at a time:

1. subject and action;
2. composition;
3. lighting;
4. style;
5. constraints.

For a revision, preserve what worked and describe only the defect and its correction. Avoid replacing the entire prompt unless the concept itself is wrong.

Do not change the default prompt from one unsatisfactory result. Record the defect, compare at least two samples, and use the thresholds in [quality-loop.md](quality-loop.md). Every changed prompt needs a new version, a fresh hash, a change summary, and the quality-event IDs that justified it.

## Brief Template

```text
Use case: [deliverable and audience]
Asset type: [orientation and image category]
Primary request: [subject, quantity, action, mandatory details]
Scene: [location, time, background, environment]
Subject details: [materials, construction, texture, contact points]
Composition: [aspect ratio, framing, placement, negative space]
Style and medium: [one medium or visual language]
Lighting and mood: [light direction, contrast, atmosphere]
Color palette: [dominant colors, accents, colors to avoid]
Text and layout: reserve clean space for later typesetting; no text, letters, logo, or watermark
Constraints: [unwanted objects, duplication, anatomy, borders, material confusion]
```
