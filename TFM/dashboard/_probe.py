import sqlite3, json
c = sqlite3.connect(r'd:\Master\TrabajoFinalUCM\TFM\dashboard\data\app.db')
c.row_factory = sqlite3.Row

def q(sql):
    return [dict(r) for r in c.execute(sql)]

print("=== EVENT TYPES ===")
for r in q("SELECT event_type, COUNT(*) n, COUNT(DISTINCT destination) nd, COUNT(DISTINCT session_id) ns FROM events GROUP BY event_type ORDER BY n DESC"):
    print(r)

print("\n=== EVENT TIMESTAMP RANGE ===")
print(q("SELECT MIN(timestamp) mn, MAX(timestamp) mx FROM events"))

print("\n=== product_impression sample (dest + metadata) ===")
for r in q("SELECT destination, page, product_id, metadata FROM events WHERE event_type='product_impression' LIMIT 8"):
    print(r)

print("\n=== product_impression destinations ===")
for r in q("SELECT destination, COUNT(*) n FROM events WHERE event_type='product_impression' GROUP BY destination ORDER BY n DESC"):
    print(r)

print("\n=== recommendation_request sample metadata ===")
for r in q("SELECT metadata FROM events WHERE event_type='recommendation_request' LIMIT 3"):
    print(r)

print("\n=== policy_recommendation sample ===")
for r in q("SELECT destination, page, metadata FROM events WHERE event_type='policy_recommendation' LIMIT 5"):
    print(r)

print("\n=== assistant_message sample ===")
for r in q("SELECT destination, page, metadata FROM events WHERE event_type='assistant_message' LIMIT 5"):
    print(r)

print("\n=== events destination coverage (all) ===")
for r in q("SELECT COALESCE(destination,'(null)') d, COUNT(*) n FROM events GROUP BY destination ORDER BY n DESC LIMIT 20"):
    print(r)

print("\n=== SESSIONS columns / sample ===")
for r in q("SELECT * FROM sessions LIMIT 3"):
    print(r)

print("\n=== sessions timestamp range ===")
print(q("SELECT MIN(started_at) mn, MAX(started_at) mx FROM sessions"))

print("\n=== destinations sample (saturation fields) ===")
for r in q("SELECT name, zone, country_name, demand, occupancy, seasonality, sustainability, reference_price_eur FROM destinations LIMIT 12"):
    print(r)

print("\n=== destination_sentiment sample ===")
for r in q("SELECT destination_name, reviews_analyzed, sentiment_score, negative_pct FROM destination_sentiment ORDER BY reviews_analyzed DESC LIMIT 10"):
    print(r)
c.close()
