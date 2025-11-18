#!/bin/bash
# Test web app endpoints and data

set -e

BASE_URL="http://localhost:8765"
PASS=0
FAIL=0

echo "=== Testing Long-Context-Bench Web App ==="
echo ""

# Test 1: Index page loads
echo "Test 1: Index page loads"
if curl -s "$BASE_URL/index.html" | grep -q "Long-Context-Bench"; then
    echo "  ✓ PASS"
    PASS=$((PASS + 1))
else
    echo "  ✗ FAIL"
    FAIL=$((FAIL + 1))
fi

# Test 2: Index.json exists and has required keys
echo "Test 2: Index.json has required keys"
KEYS=$(curl -s "$BASE_URL/index.json" | python3 -c "import sys, json; print(' '.join(json.load(sys.stdin).keys()))")
if echo "$KEYS" | grep -q "head_to_head_runs" && echo "$KEYS" | grep -q "cross_agent_runs"; then
    echo "  ✓ PASS (keys: $KEYS)"
    PASS=$((PASS + 1))
else
    echo "  ✗ FAIL (missing keys)"
    FAIL=$((FAIL + 1))
fi

# Test 3: Head-to-head data exists
echo "Test 3: Head-to-head data exists"
H2H_COUNT=$(curl -s "$BASE_URL/index.json" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['head_to_head_runs']))")
if [ "$H2H_COUNT" -gt 0 ]; then
    echo "  ✓ PASS ($H2H_COUNT head-to-head runs)"
    PASS=$((PASS + 1))
else
    echo "  ✗ FAIL (no head-to-head runs)"
    FAIL=$((FAIL + 1))
fi

# Test 4: Head-to-head file is accessible
echo "Test 4: Head-to-head file is accessible"
H2H_FILE=$(curl -s "$BASE_URL/index.json" | python3 -c "import sys, json; print(json.load(sys.stdin)['head_to_head_runs'][0]['file'])")
if curl -s "$BASE_URL/$H2H_FILE" | python3 -m json.tool > /dev/null 2>&1; then
    echo "  ✓ PASS ($H2H_FILE)"
    PASS=$((PASS + 1))
else
    echo "  ✗ FAIL (cannot access $H2H_FILE)"
    FAIL=$((FAIL + 1))
fi

# Test 5: Head-to-head data structure is correct
echo "Test 5: Head-to-head data structure"
STRUCTURE=$(curl -s "$BASE_URL/$H2H_FILE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"agents={len(data['agent_results'])} decisions={len(data['pairwise_decisions'])} stats={len(data['agent_stats'])}\")
")
if echo "$STRUCTURE" | grep -q "agents=3" && echo "$STRUCTURE" | grep -q "decisions=6"; then
    echo "  ✓ PASS ($STRUCTURE)"
    PASS=$((PASS + 1))
else
    echo "  ✗ FAIL (incorrect structure: $STRUCTURE)"
    FAIL=$((FAIL + 1))
fi

# Test 6: Cross-agent data exists
echo "Test 6: Cross-agent data exists"
CA_COUNT=$(curl -s "$BASE_URL/index.json" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['cross_agent_runs']))")
if [ "$CA_COUNT" -gt 0 ]; then
    echo "  ✓ PASS ($CA_COUNT cross-agent runs)"
    PASS=$((PASS + 1))
else
    echo "  ✗ FAIL (no cross-agent runs)"
    FAIL=$((FAIL + 1))
fi

# Test 7: Cross-agent file is accessible
echo "Test 7: Cross-agent file is accessible"
CA_FILE=$(curl -s "$BASE_URL/index.json" | python3 -c "import sys, json; print(json.load(sys.stdin)['cross_agent_runs'][0]['file'])")
if curl -s "$BASE_URL/$CA_FILE" | python3 -m json.tool > /dev/null 2>&1; then
    echo "  ✓ PASS ($CA_FILE)"
    PASS=$((PASS + 1))
else
    echo "  ✗ FAIL (cannot access $CA_FILE)"
    FAIL=$((FAIL + 1))
fi

# Test 8: JavaScript files load
echo "Test 8: JavaScript files load"
if curl -s "$BASE_URL/app.js" | grep -q "currentSummaries" && \
   curl -s "$BASE_URL/cross-agent.js" | grep -q "displayAgentDetails"; then
    echo "  ✓ PASS"
    PASS=$((PASS + 1))
else
    echo "  ✗ FAIL"
    FAIL=$((FAIL + 1))
fi

# Test 9: CSS file loads
echo "Test 9: CSS file loads"
if curl -s "$BASE_URL/styles.css" | grep -q "leaderboard"; then
    echo "  ✓ PASS"
    PASS=$((PASS + 1))
else
    echo "  ✗ FAIL"
    FAIL=$((FAIL + 1))
fi

# Test 10: Pairwise decisions have rationales
echo "Test 10: Pairwise decisions have rationales"
HAS_RATIONALE=$(curl -s "$BASE_URL/$H2H_FILE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
rationale = data['pairwise_decisions'][0].get('rationale', '')
print('yes' if len(rationale) > 50 else 'no')
")
if [ "$HAS_RATIONALE" = "yes" ]; then
    echo "  ✓ PASS"
    PASS=$((PASS + 1))
else
    echo "  ✗ FAIL"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "=== Test Results ==="
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo "  Total:  $((PASS + FAIL))"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "✓ All tests passed!"
    exit 0
else
    echo "✗ Some tests failed"
    exit 1
fi

