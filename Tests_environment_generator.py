"""
Comprehensive Test Suite - 22 Gen-1 Environments
================================================
Tests all recipes: 4 pure + 7 at 50% + 11 at 75%
"""

from environment_generator_v4_full import World
from collections import Counter

def test_all_22():
    world = World()
    
    print("=" * 80)
    print("COMPLETE GEN-1 TEST - ALL 22 ENVIRONMENTS")
    print("=" * 80)
    
    all_recipes = [
        # 100% (4)
        (['air']*4, 'sky', '100% air'),
        (['earth']*4, 'cave', '100% earth'),
        (['water']*4, 'ocean', '100% water'),
        (['fire']*4, 'inferno', '100% fire'),
        
        # 50% (7)
        (['air','air','water','water'], 'storm', '50% air + 50% water'),
        (['air','air','earth','earth'], 'hill', '50% air + 50% earth'),
        (['air','air','fire','fire'], 'wildfire', '50% air + 50% fire'),
        (['earth','earth','water','water'], 'reef', '50% earth + 50% water'),
        (['earth','earth','fire','fire'], 'basalt', '50% earth + 50% fire'),
        (['water','water','fire','fire'], 'geyser', '50% water + 50% fire'),
        
        # 75% (11)
        (['earth','earth','earth','water'], 'forest', '75% earth + 25% water'),
        (['earth','earth','earth','fire'], 'mine', '75% earth + 25% fire'),
        (['earth','earth','earth','air'], 'desert', '75% earth + 25% air'),
        (['water','water','water','earth'], 'swamp', '75% water + 25% earth'),
        (['water','water','water','fire'], 'hotspring', '75% water + 25% fire'),
        (['water','water','water','air'], 'mist', '75% water + 25% air'),
        (['fire','fire','fire','earth'], 'volcano', '75% fire + 25% earth'),
        (['fire','fire','fire','air'], 'aurora', '75% fire + 25% air'),
        (['fire','fire','fire','water'], 'lava', '75% fire + 25% water'),
        (['air','air','air','fire'], 'lightning', '75% air + 25% fire'),
        (['air','air','air','water'], 'waterfall', '75% air + 25% water'),
        (['air','air','air','earth'], 'peak', '75% air + 25% earth'),
    ]
    
    print("\nTesting exact recipes (10 runs each):\n")
    
    total_passed = 0
    failed = []
    
    for parents, expected, label in all_recipes:
        results = [world.generate(parents).name for _ in range(10)]
        counts = Counter(results)
        hit_rate = counts[expected] / 10 * 100 if expected in counts else 0
        
        if hit_rate >= 90:
            status = "✓ PASS"
            total_passed += 1
        elif hit_rate >= 70:
            status = "⚠ WEAK"
        else:
            status = "✗ FAIL"
            failed.append((expected, hit_rate, dict(counts)))
        
        print(f"  {expected:15s} ({label:30s}): {hit_rate:5.1f}% {status}")
    
    print()
    print("=" * 80)
    print(f"FINAL SCORE: {total_passed}/22 recipes with 90%+ hit rate")
    print("=" * 80)
    
    if total_passed == 22:
        print("🎉 PERFECT! All 22 recipes work correctly!")
    elif total_passed >= 20:
        print("✓ Excellent! Minor tuning needed for:")
        for name, rate, counts in failed:
            print(f"  - {name}: {rate:.1f}% (got {counts})")
    elif total_passed >= 15:
        print("⚠ Good but needs tuning for:")
        for name, rate, counts in failed:
            print(f"  - {name}: {rate:.1f}% (got {counts})")
    else:
        print("❌ Significant issues detected")
    
    return total_passed, failed

if __name__ == "__main__":
    test_all_22()