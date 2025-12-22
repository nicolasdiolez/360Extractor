# CLI AI Flag Fix Plan

## Problem Analysis
The user reported that `python src/main.py --ai true` fails. This is because `argparse` uses `action="store_true"`, which means the flag takes no arguments. Additionally, the current implementation only supports toggling "Generate Mask" mode via the `--ai` flag, missing the "Skip Frame" functionality available in the core logic.

## Proposed Changes

### 1. `src/main.py` - Argument Parsing
We will update `parse_arguments` to support explicit AI modes:
- Deprecate `--ai` (keep it as an alias for `--ai-mask` for backward compatibility or clarity).
- Add `--ai-mode` with choices `['mask', 'skip', 'none']`? Or:
- Add specific flags:
    - `--ai-mask`: Enable AI masking (equivalent to `ai_mode='Generate Mask'`).
    - `--ai-skip`: Enable AI frame skipping (equivalent to `ai_mode='Skip Frame'`).

**Decision:**
To keep it simple and aligned with standard CLI practices:
- `--ai`: Keep as a general toggle? No, better to be specific.
- Let's remove `--ai` and replace it with:
    - `--ai-mask`: Enables masking.
    - `--ai-skip`: Enables skipping.
    - (Mutually exclusive group not strictly necessary if logic handles precedence, but cleaner).
    
*Wait, if we remove `--ai`, we break existing scripts (if any).*
*Better approach:*
- Keep `--ai` as a shortcut for `--ai-mask` (current behavior).
- Add `--ai-skip` for the missing functionality.
- If both are present, what happens? `src/core/processor.py` seems to handle `ai_mode` as a single string.
    - `src/main.py` line 174: `'ai_mode': 'Generate Mask' if ai_enabled else 'None'`
    - We need to change how `settings['ai_mode']` is constructed.

**New Logic in `src/main.py`:**
```python
parser.add_argument("--ai", action="store_true", help="Enable AI Masking (Legacy alias)")
parser.add_argument("--ai-mask", action="store_true", help="Enable AI Masking (Generate Mask)")
parser.add_argument("--ai-skip", action="store_true", help="Enable AI Frame Skipping (Skip Frame)")

...

# Logic
ai_mode = 'None'
if args.ai_skip:
    ai_mode = 'Skip Frame'
elif args.ai_mask or args.ai:
    ai_mode = 'Generate Mask'
else:
    # Check config
    ai_mode = config.get('ai_mode', 'None') 
    # Handle legacy config 'ai': boolean
    if config.get('ai', False) and ai_mode == 'None':
         ai_mode = 'Generate Mask'

settings['ai_mode'] = ai_mode
```

### 2. Documentation Update
- Update `README.md` to explain:
    - `--ai-mask`: Generates masks for detected persons.
    - `--ai-skip`: Skips frames with detected persons.
    - `--ai`: Deprecated alias for `--ai-mask`.
    - Clarify flags do not take values (`true`/`false`).

## Verification Plan
1. **Reproduction:**
   - Create `tests/reproduce_cli_ai.py` that runs `python src/main.py --ai true --input ...` and expects failure/error code.
   - Run `python src/main.py --ai --input ...` and verify it runs (mocking input).

2. **Fix Verification:**
   - Run with `--ai-skip` and check logs/output to see if `ai_mode` is set correctly.
   - Run with `--ai-mask` and check.
