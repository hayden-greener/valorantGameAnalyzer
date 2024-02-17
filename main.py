import os
import re
import csv

class Parser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = {}

    def parse(self):
        with open(self.file_path) as file:
            for line in file:
                key, value = self.parse_line(line)
                if key:
                    self.parse_special_key(key, value)
                    if key not in self.data:  # Avoid overwriting special keys
                        self.data[key] = value
        self.calculate_additional_metrics()
        return self.data

    def parse_line(self, line):
        match = re.match(r"^([^:]+): (.+)$", line)
        if match:
            key, value = match.group(1).strip(), self.parse_value(match.group(2).strip())
            return key, value
        return None, None

    def parse_value(self, value):
        if value.lower() in ['true', 'false']:
            return value.lower() == 'true'
        try:
            return float(value)
        except ValueError:
            return value

    def parse_special_key(self, key, value):
        if key == "Headshot":
            self.data["Headshot %"] = float(re.search(r"\((\d+(?:\.\d+)?)%\)", value).group(1))
        elif key == "Score":
            home_rounds, away_rounds = value.split('-')
            self.data["Round Differential"] = int(home_rounds) - int(away_rounds)

    def calculate_additional_metrics(self):
        if "Start Time (UNIX)" in self.data and "End Time (UNIX)" in self.data:
            self.data["Length"] = int(self.data["End Time (UNIX)"]) - int(self.data["Start Time (UNIX)"])
        if "Damage Made" in self.data and "Damage Received" in self.data and self.data["Damage Received"] != 0:
            self.data["Damage Ratio"] = self.data["Damage Made"] / self.data["Damage Received"]

def load_weights(weights_file):
    weights = {}
    with open(weights_file) as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip the header row
        for row in reader:
            metric, target, bonus = row
            weights.setdefault(metric, []).append((float(target), float(bonus)))
    return weights

def calculate_interpolated_bonus(value, lower_bound, upper_bound, lower_bonus, upper_bonus):
    return lower_bonus if lower_bound == upper_bound else lower_bonus + (upper_bonus - lower_bonus) * ((value - lower_bound) / (upper_bound - lower_bound))

def calculate_score(data, weights):
    score = 0.0
    score_breakdown = []

    for metric, tiers in weights.items():
        metric_value = float(data.get(metric, 0))
        sorted_tiers = sorted(tiers, key=lambda x: x[0])

        for i, (target, bonus) in enumerate(sorted_tiers):
            if metric_value >= target:
                if i + 1 < len(sorted_tiers):
                    next_target, next_bonus = sorted_tiers[i + 1]
                    if metric_value < next_target:
                        interpolated_bonus = calculate_interpolated_bonus(metric_value, target, next_target, bonus, next_bonus)
                        score += interpolated_bonus
                        score_breakdown.append(f"{metric}: {metric_value}, Bonus: {interpolated_bonus:.2f})")
                        break
                else:
                    score += bonus
                    score_breakdown.append(f"{metric}: {metric_value} (Tier: {metric}:{target}:{bonus}, Bonus: {bonus})")
                    break
            elif i == 0 and metric_value < target:
                break

    return round(score, 2), score_breakdown

def load_existing_results(output_file):
    existing_results = {}
    if os.path.exists(output_file):
        with open(output_file, mode='r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                existing_results[row['Filename']] = row
    return existing_results

def main():
    content_dir = "content"
    weights_file = "weights.csv"
    output_file = "match_results.csv"

    # Load weights
    weights = load_weights(weights_file)

    # Load existing results
    existing_results = load_existing_results(output_file)
    processed_files = set(existing_results.keys())

    # Process files
    results = []
    for filename in os.listdir(content_dir):
        if filename.endswith(".md") and filename not in processed_files:
            filepath = os.path.join(content_dir, filename)
            parser = Parser(filepath)
            data = parser.parse()
            score, score_breakdown = calculate_score(data, weights)
            data['Score'] = score
            # Convert score_breakdown list to a string and save as "Log" column
            data['Log'] = '; '.join(score_breakdown)
            data['Filename'] = filename  # Track filename for identification
            results.append(data)

            # Print match analysis
            print("Match Analysis for file: {}\n".format(filename))
            for line in score_breakdown:
                print(line)
            print("\nTotal Score:", score)
            print("-" * 20)

    # Append new results to CSV
    if results:
        with open(output_file, 'a', newline='') as csvfile:
            fieldnames = results[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if not processed_files:  # File is new or empty, write header
                writer.writeheader()
                
            writer.writerows(results)

if __name__ == "__main__":
    main()