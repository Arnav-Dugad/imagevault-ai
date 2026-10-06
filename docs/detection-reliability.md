# Detection reliability

ImageVault uses conservative rules to reduce false positives. No real-world accuracy percentage has been established. Passing regression tests is evidence for the cases tested, not a claim of perfect detection.

## Why the layers matter

- SHA-256 checks exact file bytes independently of AI availability.
- Two perceptual hashes must agree before a still image can qualify as a near duplicate. A single hash collision cannot confirm it.
- Spatial verification compares normalized RGB thumbnails at 32 and 96 pixels. Both correlation and pixel error must pass. This handles ordinary resizing, JPEG compression and modest brightness changes while rejecting many rearrangements.
- Low-detail images require manual review. Matching histograms or aspect ratios alone provide little evidence.
- CLIP is a content-retrieval signal. Related subjects can have high scores without being interchangeable photos. Such suggestions always need review.
- Video/animation thumbnails are not enough to establish that whole clips are duplicates; only byte-identical clips are exact copies.
- Families require all pair relationships, rather than chaining unrelated endpoints.

The regression suite includes real pixel transformations of generated scenes, blank-image collisions, rearranged scenes, single-hash disagreement, missing verification, invalid/unnormalized vectors, conservative family grouping and unavailable AI/OCR/face models. Cloud request-limit tests execute the atomic Lua bucket through an in-memory Redis emulator.

## Honest limits

Heavy cropping, rotation, perspective changes, overlays and substantial editing may be missed by the aligned-pixel verifier. They can still appear as similar content when CLIP finds them. Small changes to screenshots or document text may be important even if the thumbnails look alike: inspect full-resolution originals before deleting. Thumbnail verification is not proof that every detail is identical. People albums, OCR and quality heuristics have separate error modes.

Before claiming accuracy in class, collect a separate, consented test set of at least 100 labeled pairs including ordinary duplicates, edits, screenshots with changed text, burst photos, unrelated look-alikes and low-detail images. Label whether each pair is byte-identical, the same underlying image, merely related, or unrelated. Keep threshold tuning images separate from final evaluation images.

For **near-duplicate** results, report precision = true positives / all predicted positives and recall = true positives / all actual positives, plus raw counts and missed cases. Do not count similar-content suggestions as confirmed duplicates. Measure on the deployed model and settings, using a fresh account or rebuilt version-6 index. Do not automatically delete this evaluation set.

The bundled six-image collection is a reproducible demonstration, not that independent benchmark. Prefer high precision for cleanup; users can manually find or review missed edits. All cleanup remains explicitly confirmed.
