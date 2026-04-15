#!/bin/bash
# ─── director_bridge.sh ──────────────────────────────────────────────────────
# AI Director bridge: calls Seed-2.0-mini (via DeepInfra) to generate
# narrative director events for injection into the holodeck MUD.
#
# Usage: director_bridge.sh <system_prompt_file> <state_prompt_file>
#   - system_prompt_file: defines the AI director's behavior and constraints
#   - state_prompt_file: current MUD state/context for the director to react to
#
# Output: parsed event text for MUD injection (or "NOTHING" if no event)
#
# This is the actualization loop's creative engine: the director reads the
# current holodeck state and decides what happens next.
# ─────────────────────────────────────────────────────────────────────────────

export DEEPINFRA_API_KEY="RhZPtvuy4cXzu02LbBSffbXeqs5Yf2IZ"

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "NOTHING"
    exit 0
fi

SYSTEM_PROMPT=$(cat "$1")
STATE_PROMPT=$(cat "$2")

RESPONSE=$(curl -s --max-time 15 "https://api.deepinfra.com/v1/openai/chat/completions" \
  -H "Authorization: Bearer $DEEPINFRA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json, sys
system = open(sys.argv[1]).read()
state = open(sys.argv[2]).read()
print(json.dumps({
    'model': 'ByteDance/Seed-2.0-mini',
    'messages': [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': state}
    ],
    'temperature': 0.9,
    'max_tokens': 60
}))
" "$1" "$2")" 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d['choices'][0]['message']['content'].strip())
except:
    print('NOTHING')
" 2>/dev/null)

if [ -z "$RESPONSE" ]; then
    echo "NOTHING"
else
    echo "$RESPONSE"
fi
