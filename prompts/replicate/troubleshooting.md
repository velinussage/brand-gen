# Troubleshooting

Common errors and solutions when using the imagevideogen skill.

## Setup Issues

### "ERROR: REPLICATE_API_TOKEN not set"

The token isn't loaded in the current shell.

```bash
# Check if token exists
cat ~/.claude/.env | grep REPLICATE

# Source it
source ~/.claude/.env

# Verify
echo "${REPLICATE_API_TOKEN:0:8}..."
```

If empty, add your token:
```bash
echo 'REPLICATE_API_TOKEN=r8_your_token_here' >> ~/.claude/.env
```

### "ERROR (401): Unauthorized"

Token is invalid or expired. Get a new one at https://replicate.com/account/api-tokens.

### "ERROR (402): Payment required"

Replicate account has no credits or billing method. Add payment at https://replicate.com/account/billing.

---

## Generation Errors

### "ERROR (422): Unprocessable Entity"

Usually means invalid input parameters. Common causes:

- **Wrong dimensions** — Some models only accept specific sizes (e.g., multiples of 8 or 64)
- **Missing required field** — Model needs a field that wasn't provided
- **Invalid aspect ratio format** — Use `16:9` not `16/9` or `1.78`

Fix: Check the model's parameter requirements in `references/models.md`.

### "ERROR: Prediction failed"

The model encountered an error during generation. Common causes:

- **Prompt too long** — Try shortening to under 100 words
- **NSFW content detected** — Adjust prompt or safety_tolerance
- **Model overloaded** — Wait a minute and retry

### "ERROR: Prediction timed out"

Generation took longer than 10 minutes. Common with:

- Video models under heavy load
- Very high resolution requests
- Complex multi-subject scenes

Fix: Retry. If persistent, try a different model or lower resolution.

### "ERROR: Rate limited too many times"

Hit Replicate API rate limits. The script retries with exponential backoff up to 5 times.

Fix: Wait 30-60 seconds and retry. Consider upgrading your Replicate plan for higher limits.

### "ERROR: No output in prediction result"

Model completed but returned no output. Rare, usually a Replicate-side issue.

Fix: Retry. If persistent, try a different model version.

---

## Quality Issues

### Image looks generic/flat

**Cause:** Missing style and lighting descriptors.

**Fix:** Add specifics:
```
# Bad
-p "a mountain"

# Good
-p "Snow-capped mountain peak at golden hour, dramatic clouds, wide angle lens, HDR, vivid warm colors"
```

### Wrong style/mood

**Cause:** Prompt doesn't specify style clearly enough.

**Fix:** Front-load the style descriptor or use a preset:
```bash
# Use preset
--preset landscape

# Or be explicit about style
-p "Oil painting style, impressionist brushwork, a village by a river..."
```

### Distorted faces/hands

**Cause:** Common AI generation artifact.

**Fix:**
- Add negative prompt: `-n "deformed, distorted, extra fingers, mutated hands"`
- Use flux-pro (best at faces)
- For video portraits, use kling (best facial detail)

### Video has morphing/warping artifacts

**Cause:** Too much motion requested, or conflicting motion descriptions.

**Fix:**
- Reduce motion complexity
- Use shorter duration
- Add "subtle" or "gentle" modifiers
- For I2V, describe only motion (not the scene)

### Video subject changes appearance

**Cause:** Temporal inconsistency, common with longer videos.

**Fix:**
- Use shorter duration (3-5s)
- Use kling for portraits (best identity consistency)
- Keep camera motion simple
- Avoid dramatic lighting changes in prompt

### Output file is 0 bytes

**Cause:** Download failed or model returned empty output.

**Fix:** Check network connection and retry. The script should report an error if the download fails.

---

## Model-Specific Issues

### flux-pro: "prompt_upsampling" warning

This is informational — prompt upsampling auto-enhances your prompt. It's enabled by default and generally improves results. To disable, you'd need to modify models.json defaults.

### sdxl: Results too noisy

Increase inference steps:
```bash
--steps 40 -g 8.0
```

### kling: Video too short

Increase duration:
```bash
-d 10  # up to 10 seconds
```

### veo: Very expensive generation

Veo costs $0.40/second. An 8-second video costs ~$3.20. Use luma ($0.032/s) or kling ($0.07/s) for drafts, then veo for final quality.

---

## File Issues

### Output saved as wrong format

The script auto-selects format based on model defaults (WebP for Flux, PNG for SDXL, MP4 for video). Override with `-o filename.ext`:

```bash
-o my_image.png    # Force PNG
-o my_video.mp4    # Force MP4
```

Note: This only changes the file extension, not the actual encoding. The model determines the actual format.

### Can't open WebP files

WebP is supported by most modern tools. If your viewer doesn't support it:
- macOS Preview supports WebP natively
- Use `sips -s format png input.webp --out output.png` to convert on macOS
