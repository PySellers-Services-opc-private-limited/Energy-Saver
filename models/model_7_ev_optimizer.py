"""
Step 8: EV Charging Optimizer (Reinforcement Learning)
========================================================
Uses a Q-Learning agent to decide the BEST time to
charge your electric vehicle, minimizing cost while
ensuring the car is ready when you need it.

State space:
  - Current battery % (0–100)
  - Hour of day (0–23)
  - Current electricity tariff (low/mid/peak)
  - Solar surplus available (kWh)
  - Departure time proximity (hours left)

Actions:
  0 = Don't charge
  1 = Charge at slow rate (1.4 kW)
  2 = Charge at fast rate (7.2 kW)

Reward:
  + Reward for having battery ready before departure
  + Reward for charging during solar surplus
  - Penalty for charging during peak tariff
  - Penalty for not being ready at departure time
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
os.makedirs("outputs", exist_ok=True)
os.makedirs("models",  exist_ok=True)

print("\n" + "="*55)
print("  STEP 8: EV CHARGING OPTIMIZER (Q-LEARNING)")
print("="*55)

# ─────────────────────────────────────────
# 1. ENVIRONMENT SETUP
# ─────────────────────────────────────────

# EV specs
EV_BATTERY_KWH   = 60.0   # 60 kWh battery
EV_EFFICIENCY    = 0.9    # 90% charging efficiency
SLOW_CHARGE_KW   = 1.4    # Level 1: slow
FAST_CHARGE_KW   = 7.2    # Level 2: fast
TARGET_SOC       = 0.85   # Target: 85% charge
DEPARTURE_HOUR   = 8      # Leave at 8 AM

# Tariff schedule ($/kWh)
TARIFFS = {h: 0.08 if h < 7 or h >= 21 else (0.22 if 17 <= h <= 20 else 0.13)
           for h in range(24)}

def get_tariff_level(hour):
    t = TARIFFS[hour]
    if t <= 0.09:   return 0   # Off-peak
    elif t <= 0.15: return 1   # Mid-peak
    else:           return 2   # Peak

def get_solar_surplus(hour):
    """Simulated solar surplus available for EV charging"""
    if 9 <= hour <= 16:
        return max(0, 3.0 * np.sin((hour - 9) * np.pi / 7) + np.random.normal(0, 0.5))
    return 0.0

# ─────────────────────────────────────────
# 2. Q-LEARNING AGENT
# ─────────────────────────────────────────
print("\n🤖 Initializing Q-Learning agent...")

# Discretize state space
SOC_BINS     = 10   # Battery: 0–100% in 10% steps
HOUR_BINS    = 24   # 0–23 hours
TARIFF_BINS  = 3    # low / mid / peak
SOLAR_BINS   = 3    # none / some / lots
DEPART_BINS  = 8    # hours until departure (0–7+)
N_ACTIONS    = 3    # don't charge / slow / fast

Q = np.zeros((SOC_BINS, HOUR_BINS, TARIFF_BINS, SOLAR_BINS, DEPART_BINS, N_ACTIONS))

def encode_state(soc_pct, hour, solar_kw):
    soc_bin    = min(int(soc_pct / 10), SOC_BINS - 1)
    tariff_bin = get_tariff_level(hour)
    solar_bin  = min(int(solar_kw / 1.5), SOLAR_BINS - 1)
    hours_left = (DEPARTURE_HOUR - hour) % 24
    depart_bin = min(hours_left, DEPART_BINS - 1)
    return (soc_bin, hour, tariff_bin, solar_bin, depart_bin)

def compute_reward(action, soc_pct, hour, solar_kw, new_soc_pct):
    reward = 0.0
    tariff = TARIFFS[hour]

    if action == 0:
        # Penalize for not charging if battery is low and departure is close
        hours_left = (DEPARTURE_HOUR - hour) % 24
        if soc_pct < TARGET_SOC * 100 and hours_left <= 3:
            reward -= 10.0
    else:
        charge_kw = SLOW_CHARGE_KW if action == 1 else FAST_CHARGE_KW

        # Cost penalty
        reward -= tariff * charge_kw * 0.5  # Half-hour step cost

        # Bonus for using solar surplus
        if solar_kw > 0.5:
            reward += min(solar_kw, charge_kw) * 0.3

        # Bonus for charging toward target
        if new_soc_pct <= TARGET_SOC * 100:
            reward += 0.5

    # Big reward for being ready at departure
    if hour == DEPARTURE_HOUR and soc_pct >= TARGET_SOC * 100:
        reward += 20.0

    # Penalty for overcharging
    if new_soc_pct > 95:
        reward -= 2.0

    return reward

def step(soc_pct, action, hour, solar_kw):
    """Apply action, return new SOC"""
    if action == 0:
        return soc_pct  # No charging

    charge_kw = SLOW_CHARGE_KW if action == 1 else FAST_CHARGE_KW
    charge_kwh = charge_kw * 0.5 * EV_EFFICIENCY   # 30-min step
    delta_soc = (charge_kwh / EV_BATTERY_KWH) * 100
    new_soc = min(100.0, soc_pct + delta_soc)
    return new_soc

# ─────────────────────────────────────────
# 3. TRAIN Q-LEARNING AGENT
# ─────────────────────────────────────────
print("\n🚀 Training Q-Learning agent (1000 episodes)...")

EPISODES     = 1000
ALPHA        = 0.1    # Learning rate
GAMMA        = 0.95   # Discount factor
EPSILON      = 1.0    # Exploration rate
EPSILON_MIN  = 0.05
EPSILON_DECAY = 0.995

episode_rewards = []
episode_final_soc = []

for episode in range(EPISODES):
    # Random start conditions
    soc_pct    = np.random.uniform(10, 40)   # Start with low battery
    total_reward = 0

    for step_num in range(48):   # 48 half-hour steps = 24 hours
        hour = (18 + step_num // 2) % 24    # Start at 6 PM (after work)
        solar_kw = get_solar_surplus(hour)

        state = encode_state(soc_pct, hour, solar_kw)

        # Epsilon-greedy action selection
        if np.random.random() < EPSILON:
            action = np.random.randint(N_ACTIONS)
        else:
            action = np.argmax(Q[state])

        new_soc = step(soc_pct, action, hour, solar_kw)
        reward  = compute_reward(action, soc_pct, hour, solar_kw, new_soc)

        next_hour   = (hour + 1) % 24
        next_solar  = get_solar_surplus(next_hour)
        next_state  = encode_state(new_soc, next_hour, next_solar)

        # Q-update
        Q[state][action] += ALPHA * (
            reward + GAMMA * np.max(Q[next_state]) - Q[state][action]
        )

        soc_pct = new_soc
        total_reward += reward

    EPSILON = max(EPSILON_MIN, EPSILON * EPSILON_DECAY)
    episode_rewards.append(total_reward)
    episode_final_soc.append(soc_pct)

    if (episode + 1) % 200 == 0:
        avg_reward = np.mean(episode_rewards[-200:])
        avg_soc    = np.mean(episode_final_soc[-200:])
        print(f"   Episode {episode+1:4d} | Avg Reward: {avg_reward:7.2f} | Avg Final SOC: {avg_soc:.1f}%")

# ─────────────────────────────────────────
# 4. SIMULATE OPTIMAL CHARGING SCHEDULE
# ─────────────────────────────────────────
print("\n📋 Simulating optimal charging schedule (6 PM → 8 AM)...")
soc_pct = 25.0
schedule = []

for step_num in range(28):   # 6 PM to 8 AM = 14 hrs = 28 half-steps
    hour     = (18 + step_num // 2) % 24
    solar_kw = get_solar_surplus(hour)
    state    = encode_state(soc_pct, hour, solar_kw)
    action   = np.argmax(Q[state])

    action_names = ["⛔ No Charge", "🔋 Slow (1.4kW)", "⚡ Fast (7.2kW)"]
    cost = TARIFFS[hour] * ([0, SLOW_CHARGE_KW, FAST_CHARGE_KW][action]) * 0.5

    schedule.append({
        "hour":       f"{hour:02d}:{'00' if step_num%2==0 else '30'}",
        "action":     action_names[action],
        "tariff":     f"${TARIFFS[hour]:.2f}",
        "solar_kw":   round(solar_kw, 2),
        "battery_pct": round(soc_pct, 1),
        "cost_step":  round(cost, 4)
    })

    soc_pct = step(soc_pct, action, hour, solar_kw)

sched_df = pd.DataFrame(schedule)
print("\n⚡ Optimal EV Charging Schedule:")
print("─" * 70)
print(sched_df.to_string(index=False))

total_cost = sched_df["cost_step"].sum()
final_soc  = soc_pct
print(f"\n   💰 Total charging cost: ${total_cost:.4f}")
print(f"   🔋 Final battery level: {final_soc:.1f}%")

# ─────────────────────────────────────────
# 5. PLOT
# ─────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("EV Charging Optimizer (Q-Learning) - Results", fontsize=14, fontweight="bold")

# Plot 1: Training rewards
window = 50
smoothed = pd.Series(episode_rewards).rolling(window).mean()
axes[0,0].plot(episode_rewards, alpha=0.3, color="blue", label="Raw")
axes[0,0].plot(smoothed, color="blue", linewidth=2, label=f"{window}-ep avg")
axes[0,0].set_title("Training Rewards per Episode")
axes[0,0].set_xlabel("Episode"); axes[0,0].set_ylabel("Total Reward")
axes[0,0].legend(); axes[0,0].grid(True, alpha=0.3)

# Plot 2: Final SOC over training
smoothed_soc = pd.Series(episode_final_soc).rolling(window).mean()
axes[0,1].plot(episode_final_soc, alpha=0.2, color="green")
axes[0,1].plot(smoothed_soc, color="green", linewidth=2)
axes[0,1].axhline(TARGET_SOC * 100, color="red", linestyle="--", label=f"Target {TARGET_SOC*100:.0f}%")
axes[0,1].set_title("Final Battery % at Departure (over training)")
axes[0,1].set_xlabel("Episode"); axes[0,1].set_ylabel("SOC (%)")
axes[0,1].legend(); axes[0,1].grid(True, alpha=0.3)

# Plot 3: Charging schedule - battery level
hours_labels = sched_df["hour"].tolist()
battery_vals = sched_df["battery_pct"].tolist()
action_colors = {"⛔ No Charge": "gray", "🔋 Slow (1.4kW)": "steelblue", "⚡ Fast (7.2kW)": "green"}
bar_colors = [action_colors[a] for a in sched_df["action"]]
axes[1,0].bar(range(len(sched_df)), sched_df["battery_pct"], color=bar_colors, alpha=0.7)
axes[1,0].axhline(TARGET_SOC * 100, color="red", linestyle="--", label="Target SOC")
axes[1,0].set_xticks(range(0, len(sched_df), 2))
axes[1,0].set_xticklabels(hours_labels[::2], rotation=45, fontsize=7)
axes[1,0].set_title("Battery % by Time Slot"); axes[1,0].set_ylabel("Battery (%)")
axes[1,0].legend(); axes[1,0].grid(True, alpha=0.3, axis="y")

# Plot 4: Tariff timeline
tariff_vals = [float(TARIFFS[h]) for h in range(24)]
bar_t_colors = ["green" if t <= 0.09 else ("red" if t >= 0.20 else "orange") for t in tariff_vals]
axes[1,1].bar(range(24), tariff_vals, color=bar_t_colors, alpha=0.8)
axes[1,1].set_title("Electricity Tariff Schedule")
axes[1,1].set_xlabel("Hour of Day"); axes[1,1].set_ylabel("$/kWh")
axes[1,1].grid(True, alpha=0.3, axis="y")
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor="green", label="Off-peak"),
                   Patch(facecolor="orange", label="Mid-peak"),
                   Patch(facecolor="red",   label="Peak")]
axes[1,1].legend(handles=legend_elements)

plt.tight_layout()
plt.savefig("outputs/model7_ev_optimizer_results.png", dpi=150)
print("\n   📊 Plot saved → outputs/model7_ev_optimizer_results.png")

np.save("models/ev_q_table.npy", Q)
sched_df.to_csv("outputs/ev_charging_schedule.csv", index=False)
print("✅ Step 8 Complete! EV optimizer saved.\n")
