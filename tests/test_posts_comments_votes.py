def make_post(client, headers, title="Hello", content="World", published=True):
    r = client.post("/posts/", json={"title": title, "content": content, "published": published}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ---------- posts ----------

def test_create_post_defaults_to_published_and_hides_owner_email(client, alice):
    _, h = alice
    r = client.post("/posts/", json={"title": "t", "content": "c"}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["published"] is True
    assert body["owner"]["username"] == "alice"
    assert "email" not in body["owner"]


def test_post_validation(client, alice):
    _, h = alice
    assert client.post("/posts/", json={"title": "", "content": "c"}, headers=h).status_code == 422
    assert client.post("/posts/", json={"title": "t" * 201, "content": "c"}, headers=h).status_code == 422
    assert client.post("/posts/", json={"title": "t"}, headers=h).status_code == 422


def test_drafts_are_private_to_their_owner(client, alice, bob):
    _, a = alice
    _, b = bob
    draft = make_post(client, a, "secret draft", published=False)
    make_post(client, a, "public one")

    assert [p["Post"]["title"] for p in client.get("/posts/", headers=b).json()] == ["public one"]
    assert len(client.get("/posts/", headers=a).json()) == 2
    assert client.get(f"/posts/{draft['id']}", headers=b).status_code == 404
    assert client.get(f"/posts/{draft['id']}", headers=a).status_code == 200
    # Other people cannot touch, vote on or comment on it either:
    assert client.put(f"/posts/{draft['id']}", json={"title": "x", "content": "y"}, headers=b).status_code == 404
    assert client.delete(f"/posts/{draft['id']}", headers=b).status_code == 404
    assert client.post("/vote/", json={"post_id": draft["id"], "dir": 1}, headers=b).status_code == 404
    assert client.post(f"/posts/{draft['id']}/comments", json={"content": "hi"}, headers=b).status_code == 404


def test_only_owner_can_update_or_delete(client, alice, bob):
    _, a = alice
    _, b = bob
    post = make_post(client, a)
    assert client.put(f"/posts/{post['id']}", json={"title": "x", "content": "y"}, headers=b).status_code == 403
    assert client.delete(f"/posts/{post['id']}", headers=b).status_code == 403
    r = client.put(f"/posts/{post['id']}", json={"title": "new", "content": "text"}, headers=a)
    assert r.status_code == 200 and r.json()["title"] == "new"
    assert client.delete(f"/posts/{post['id']}", headers=a).status_code == 204
    assert client.get(f"/posts/{post['id']}", headers=a).status_code == 404


def test_pagination_is_stable_and_reports_total(client, alice):
    _, h = alice
    for i in range(7):
        make_post(client, h, f"post {i}")
    seen = []
    for skip in (0, 3, 6):
        r = client.get(f"/posts/?limit=3&skip={skip}", headers=h)
        assert r.headers["X-Total-Count"] == "7"
        seen += [p["Post"]["id"] for p in r.json()]
    assert len(seen) == 7 and len(set(seen)) == 7
    assert seen == sorted(seen, reverse=True)  # newest first
    assert client.get("/posts/?limit=0", headers=h).status_code == 422
    assert client.get("/posts/?limit=500", headers=h).status_code == 422


def test_sorting_search_and_owner_filter(client, alice, bob):
    _, a = alice
    _, b = bob
    old = make_post(client, a, "Old post", "about cats")
    mid = make_post(client, b, "Mid post", "about dogs")
    new = make_post(client, a, "New post", "100% sure_thing")

    ids = lambda path, h=a: [p["Post"]["id"] for p in client.get(path, headers=h).json()]
    assert ids("/posts/?sort=oldest") == [old["id"], mid["id"], new["id"]]
    assert ids("/posts/?sort=newest") == [new["id"], mid["id"], old["id"]]

    client.post("/vote/", json={"post_id": mid["id"], "dir": 1}, headers=a)
    client.post("/vote/", json={"post_id": mid["id"], "dir": 1}, headers=b)
    client.post("/vote/", json={"post_id": old["id"], "dir": 1}, headers=a)
    assert ids("/posts/?sort=top")[:2] == [mid["id"], old["id"]]

    client.post(f"/posts/{old['id']}/comments", json={"content": "c1"}, headers=a)
    assert ids("/posts/?sort=discussed")[0] == old["id"]

    assert ids("/posts/?search=CATS") == [old["id"]]          # case-insensitive, searches content
    assert ids("/posts/?search=mid") == [mid["id"]]
    assert ids("/posts/?search=100%25") == [new["id"]]         # % is literal, not a wildcard
    assert ids("/posts/?search=%25") == [new["id"]]
    assert ids("/posts/?owner=BOB") == [mid["id"]]
    assert client.get("/posts/?sort=bogus", headers=a).status_code == 422


def test_counts_are_not_multiplied_by_joins(client, alice, bob):
    """3 likes x 4 comments must show 3 and 4, not 12."""
    _, a = alice
    _, b = bob
    from tests.conftest import register, login
    c_user = register(client, "carol")
    c = login(client, "carol")
    post = make_post(client, a)
    for h in (a, b, c):
        assert client.post("/vote/", json={"post_id": post["id"], "dir": 1}, headers=h).status_code == 201
    for i in range(4):
        client.post(f"/posts/{post['id']}/comments", json={"content": f"c{i}"}, headers=b)
    item = client.get(f"/posts/{post['id']}", headers=a).json()
    assert item["votes"] == 3 and item["comments"] == 4 and item["voted"] is True


# ---------- votes ----------

def test_vote_rules(client, alice, bob):
    _, a = alice
    _, b = bob
    post = make_post(client, a)
    assert client.post("/vote/", json={"post_id": post["id"], "dir": 1}, headers=b).status_code == 201
    assert client.post("/vote/", json={"post_id": post["id"], "dir": 1}, headers=b).status_code == 409
    assert client.get(f"/posts/{post['id']}", headers=b).json()["voted"] is True
    assert client.get(f"/posts/{post['id']}", headers=a).json()["voted"] is False
    assert client.post("/vote/", json={"post_id": post["id"], "dir": 0}, headers=b).status_code == 201
    assert client.post("/vote/", json={"post_id": post["id"], "dir": 0}, headers=b).status_code == 404
    assert client.post("/vote/", json={"post_id": 9999, "dir": 1}, headers=b).status_code == 404
    assert client.post("/vote/", json={"post_id": post["id"], "dir": 2}, headers=b).status_code == 422


# ---------- comments ----------

def test_comment_lifecycle_and_permissions(client, alice, bob, make_user):
    _, a = alice
    _, b = bob
    _, c = make_user("carol")
    post = make_post(client, a)

    r = client.post(f"/posts/{post['id']}/comments", json={"content": "  nice post  "}, headers=b)
    assert r.status_code == 201
    comment = r.json()
    assert comment["content"] == "nice post" and comment["author"]["username"] == "bob"
    assert "email" not in comment["author"]

    assert client.post(f"/posts/{post['id']}/comments", json={"content": "   "}, headers=b).status_code == 422
    assert client.post(f"/posts/{post['id']}/comments", json={"content": "x" * 1001}, headers=b).status_code == 422
    assert client.post("/posts/9999/comments", json={"content": "x"}, headers=b).status_code == 404

    listed = client.get(f"/posts/{post['id']}/comments", headers=c).json()
    assert [x["content"] for x in listed] == ["nice post"]

    assert client.delete(f"/comments/{comment['id']}", headers=c).status_code == 403   # stranger
    assert client.delete(f"/comments/{comment['id']}", headers=a).status_code == 204   # post owner
    assert client.delete(f"/comments/{comment['id']}", headers=a).status_code == 404

    own = client.post(f"/posts/{post['id']}/comments", json={"content": "mine"}, headers=b).json()
    assert client.delete(f"/comments/{own['id']}", headers=b).status_code == 204       # author


def test_deleting_a_post_removes_its_comments_and_votes(client, alice, bob):
    from sqlalchemy import text
    from app.database import engine
    _, a = alice
    _, b = bob
    post = make_post(client, a)
    client.post(f"/posts/{post['id']}/comments", json={"content": "x"}, headers=b)
    client.post("/vote/", json={"post_id": post["id"], "dir": 1}, headers=b)
    assert client.delete(f"/posts/{post['id']}", headers=a).status_code == 204
    with engine.connect() as conn:
        assert conn.execute(text("select count(*) from comments")).scalar() == 0
        assert conn.execute(text("select count(*) from votes")).scalar() == 0
