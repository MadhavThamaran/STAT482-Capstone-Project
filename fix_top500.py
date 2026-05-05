import sys, re
sys.stdout.reconfigure(encoding='utf-8')

raw = open('data/raw/top_500_movies.csv', encoding='utf-8').read()
lines = raw.strip().split('\n')

header = lines[0]
rows = [header]

for line in lines[1:]:
    # Format per line: Rank,Title,$digits,digits,digits,Year
    # Year is 4 digits at end, Rank is integer at start
    # Gross is $NNN,NNN,NNN — has commas inside
    m = re.match(r'^(\d+),(.+),(\$[\d,]+),(\d{4})$', line)
    if m:
        rank = m.group(1)
        title = m.group(2)
        gross = m.group(3).replace(',', '')  # strip commas from dollar amount
        year = m.group(4)
        rows.append(f'{rank},{title},{gross},{year}')
    else:
        rows.append(line)

open('data/raw/top_500_movies.csv', 'w', encoding='utf-8').write('\n'.join(rows) + '\n')
print(f'Fixed {len(rows)-1} data rows')

# Verify
import pandas as pd
df = pd.read_csv('data/raw/top_500_movies.csv', encoding='utf-8')
df['Domestic Gross'] = df['Domestic Gross'].astype(str).str.replace('$','',regex=False).str.replace(',','',regex=False)
df['Domestic Gross'] = pd.to_numeric(df['Domestic Gross'], errors='coerce')
df.to_csv('data/raw/top_500_movies.csv', index=False, encoding='utf-8-sig')
print(df.shape)
print(df.head(5).to_string())
