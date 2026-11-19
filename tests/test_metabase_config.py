from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def test_seller_questions_join_the_seller_dimension():
    source = (PROJECT / "metabase" / "provision_metabase.py").read_text(encoding="utf-8")

    assert "SELECT s.seller_name, SUM(sd.total_revenue)" in source
    assert "JOIN dwh.dim_seller s USING(seller_id)" in source
    assert "WHERE sd.dt=(SELECT MAX(dt) FROM analytics.seller_daily)" in source


def test_required_dashboard_views_are_provisioned():
    source = (PROJECT / "metabase" / "provision_metabase.py").read_text(encoding="utf-8")

    assert "Top 5 vendeurs du jour" in source
    assert "Top 10 vendeurs du mois" in source
    assert "Evolution des 3 meilleurs vendeurs (30 jours)" in source
    assert "Vendeurs sans vente depuis 7 jours" in source
    assert "Commissions - Sport" in source
    assert "Ventes par catégorie - Sport" in source


def test_provisioning_updates_existing_questions_and_dashboard_cards():
    source = (PROJECT / "metabase" / "provision_metabase.py").read_text(encoding="utf-8")

    assert 'call("PUT", f"/api/card/{card[\'id\']}", json=card_payload)' in source
    assert 'call("PUT", f"/api/dashboard/{dashboard[\'id\']}", json={"dashcards": dashcards})' in source
