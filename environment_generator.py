# Hardcoded environment times (seconds) for testing.
air_time = 15.0
earth_time = 35.0
water_time = 50.0


def generate_next_environment(air: float, earth: float, water: float):
    # TODO: Implement environment generation algorithm.
    # Intentionally left blank for experimentation with multiple approaches.
    return None


def main():
    result = generate_next_environment(air_time, earth_time, water_time)
    total_time = air_time + earth_time + water_time
    if total_time > 0:
        air_ratio = air_time / total_time
        earth_ratio = earth_time / total_time
        water_ratio = water_time / total_time
    else:
        air_ratio = 0.0
        earth_ratio = 0.0
        water_ratio = 0.0

    print(f"Input Times -> air: {air_time}, earth: {earth_time}, water: {water_time}")
    print(f"Ratios -> air: {air_ratio:.3f}, earth: {earth_ratio:.3f}, water: {water_ratio:.3f}")
    print(f"Generated Environment -> {result}")


if __name__ == "__main__":
    main()
