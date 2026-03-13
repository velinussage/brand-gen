# Setup

<required_reading>
Before starting: none (this is the first workflow).
</required_reading>

<process>

## 1. Get Replicate API Token

1. Sign up at https://replicate.com
2. Go to https://replicate.com/account/api-tokens
3. Create a new token (starts with `r8_`)
4. Add to `~/.claude/.env`:

```bash
echo 'REPLICATE_API_TOKEN=r8_your_token_here' >> ~/.claude/.env
```

## 2. Verify Token

```bash
source ~/.claude/.env
python3 .claude/skills/imagevideogen/scripts/generate.py image --list-models
```

If the models list appears, setup is complete.

## 3. Test Generation

```bash
source ~/.claude/.env
python3 .claude/skills/imagevideogen/scripts/generate.py image \
  -m flux-schnell -p "A red fox in a snowy forest" -o test_fox.webp
```

Check that `test_fox.webp` was created and contains the expected image.
Cost: ~$0.003 (cheapest model).

## 4. Clean Up Test File

```bash
rm -f test_fox.webp
```

</process>

<success_criteria>
- REPLICATE_API_TOKEN is set in ~/.claude/.env
- `--list-models` shows available models without errors
- Test image generates and downloads successfully
</success_criteria>
