# Conversation Safety Documentation

This document describes the safety mechanisms implemented in the Relab Chatbot to prevent conversational loops, abusive handoffs, and runtime errors.

## 1. Canonical State Contract

### 1.1 Variant Format (`VariantDict`)

All product variants MUST follow this strict format:

```python
class VariantDict(TypedDict, total=False):
    id: str
    model: str
    price: int
    storage: str
    battery: int
    grade: str
    color: str
```

**Rules:**
- `available_variants` is ONLY populated after displaying a product list
- `selected_variant` MUST be a complete `VariantDict`, never a partial dict or index
- No mixing of formats allowed

### 1.2 Selection Lock

```python
selection_locked: bool = False
```

Once `selection_locked = True`:
- `FlowAction.SHOW_PRODUCT_LIST` is **strictly forbidden**
- Flow is hijacked to `CONFIRM_AND_ASK` or next logical step

### 1.3 Repetition Detection

```python
last_bot_message_hash: Optional[str] = None
repeat_count: int = 0
```

- Hash is computed from normalized (lowercase, trimmed) message
- Used to detect when bot is about to send identical responses

---

## 2. Anti-Loop Rules

### 2.1 Relisting Prevention

A product list will **NEVER** be shown if any of these conditions are true:

| Condition | Check |
|-----------|-------|
| Selection locked | `qualification_data.selection_locked == True` |
| Current selection exists | `qualification_data.extra_data.get("current_selection")` |
| Confirmed variant exists | `qualification_data.extra_data.get("confirmed_variant")` |

**Implementation**: See `ChatService.process_message()` lines 358-363.

### 2.2 Repetition Strategy

| Count | Strategy |
|-------|----------|
| 1 | Normal response |
| 2 | Clarification question (change approach) |
| 3+ | Soft handoff offer (user must confirm) |

**Note**: Handoff is NEVER forced. User must explicitly confirm.

---

## 3. Handoff Rules

### 3.1 Strict Gates (NEVER Handoff)

| Condition | Reason |
|-----------|--------|
| `FlowAction.COMPLETE` | Order is complete, no human needed |
| `IntentType.UNKNOWN` | Bot should clarify, not escalate |
| Payment/credit questions | Bot should answer first |

### 3.2 Valid Handoff Triggers

| Trigger | `HandoffReason` |
|---------|-----------------|
| User explicitly asks for human | `EXPLICIT_REQUEST` |
| SAV intent | `COMPLEX_SAV` |
| Complex repair (water, motherboard) | `COMPLEX_SAV` |
| 3+ consecutive failures | `RECOVERY_FAILURE` |

### 3.3 Logging

Every handoff decision is logged:

```python
logger.info(f"✅ Handoff triggered: EXPLICIT_REQUEST")
logger.info(f"🚫 Handoff blocked: COMPLETE action does not trigger handoff")
```

---

## 4. Natural Language Selection

The bot handles these selection patterns:

| Pattern | Example | Resolution |
|---------|---------|------------|
| Price | "celui à 7 590 dhs" | Match variant by price (±50 MAD tolerance) |
| Index | "le 4", "le premier", "le dernier" | Select by position |
| Superlative | "le moins cher", "le meilleur" | min/max by attribute |
| Attribute | "le 256Go bleu" | Match by storage + color |
| Darija | "louwel", "rkhes" | Same as French equivalents |

**Normalization**: All input is normalized (accents removed, currency unified, spaces normalized).

---

## 5. Debugging Guide

### 5.1 Common Issues

#### "Bot keeps relisting products"
1. Check `selection_locked` in qualification_data
2. Check `extra_data.current_selection`
3. Verify `extract_selection_explicit()` returned a valid variant

#### "Unexpected handoff"
1. Check logs for `HandoffReason`
2. Verify intent is not `SAV` or `HUMAIN`
3. Check `repeat_count` (should be < 3)

#### "Selection not recognized"
1. Check if `available_variants` is populated
2. Test with `normalize_user_input()` to see normalized text
3. Verify price tolerance (±50 MAD)

### 5.2 Useful Logs

```python
# Selection lock
logger.info("🔒 Selection lock ACTIVE. Hijacking SHOW_PRODUCT_LIST to CONFIRM_AND_ASK.")

# Repetition
logger.warning(f"⚠️ Repetition detected (count={qualification_data.repeat_count})")

# Handoff
logger.info(f"✅ Handoff triggered: RECOVERY_FAILURE (repeat_count=3)")
logger.info(f"🚫 Handoff blocked: UNKNOWN intent does not trigger handoff")
```

### 5.3 Testing Locally

```bash
# Run safety tests
PYTHONPATH=. pytest tests/test_conversation_safety.py -v

# Test specific selection
python -c "
from logic.qualification import qualification_engine
variants = [{'price': 5990}, {'price': 7590}]
result = qualification_engine.extract_selection_explicit('celui à 7 590', variants)
print(result)
"
```

---

## 6. Test Coverage

All safety rules are tested in `tests/test_conversation_safety.py`:

| Test Class | Scenarios |
|------------|-----------|
| `TestGreetingNoHandoff` | "bonjour", "salam" |
| `TestPriceSelection` | "7 590 dhs", "7590", "6590 mad" |
| `TestSuperlativeSelection` | "le moins cher", "le plus cher", "rkhes" |
| `TestIndexSelection` | "le 4", "le premier", "le dernier", "louwel" |
| `TestCOMPLETENoHandoff` | COMPLETE action |
| `TestUNKNOWNNoHandoff` | UNKNOWN intent |
| `TestRecoveryFailureHandoff` | repeat_count >= 3 |
| `TestExplicitHumanRequest` | "parler à un humain" |
| `TestNormalization` | Accents, currency |
| `TestMessageHash` | Hash consistency |

**Run tests before every deployment.**
