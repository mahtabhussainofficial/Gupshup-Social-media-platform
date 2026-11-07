/* Gupshup frontend: plain JavaScript, no framework.
 *
 * Safety rule used everywhere: text from users is only ever put on the page with
 * textContent / createTextNode (through the h() helper below), never with innerHTML,
 * so a post containing <script> is shown as text instead of running.
 */
"use strict";

const TOKEN_KEY = "gupshup_token";
const token = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

// ---------- small helpers ----------

/** h("a", {href: "/x", class: "y", onclick: fn}, "text", childNode) -> element */
function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}

class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

function describeError(detail) {
  if (Array.isArray(detail)) {  // FastAPI validation errors
    return detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`.replace(/^: /, "")).join(". ");
  }
  return typeof detail === "string" ? detail : "Something went wrong";
}

/** Calls the API. Returns {data, res}. Throws ApiError on failure. */
async function api(path, { method = "GET", json, body, auth = true } = {}) {
  const headers = {};
  const t = token.get();
  if (auth && t) headers.Authorization = `Bearer ${t}`;
  if (json !== undefined) headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(path, { method, headers, body: json !== undefined ? JSON.stringify(json) : body });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection.");
  }
  if (res.status === 401 && auth && t) {  // token expired or invalid
    token.clear();
    location.href = "/login?next=" + encodeURIComponent(location.pathname + location.search);
    throw new ApiError(401, "Please log in again");
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, describeError(data && data.detail));
  return { data, res };
}

const $ = (selector) => document.querySelector(selector);

function notice(message, kind = "error") {
  const el = $("#notice");
  if (!el) return;
  el.textContent = message;
  el.className = `notice ${kind}`;
  el.hidden = false;
  el.scrollIntoView({ block: "nearest" });
}
function clearNotice() { const el = $("#notice"); if (el) el.hidden = true; }

/** Runs `fn` for a form submit with the button disabled and errors shown in the notice bar. */
function onSubmit(form, fn) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearNotice();
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    try { await fn(new FormData(form)); }
    catch (err) { notice(err.message); }
    finally { button.disabled = false; }
  });
}

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function safeNext() {
  const next = new URLSearchParams(location.search).get("next");
  // Only same-site paths: "//evil.com" and "https://..." are ignored (open-redirect protection).
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

let me = null;  // the logged-in user, filled by requireLogin()/loadNav()

async function loadNav() {
  const nav = $("#nav");
  nav.replaceChildren();
  if (!token.get()) {
    nav.append(h("a", { href: "/login" }, "Log in"), h("a", { href: "/register" }, "Sign up"));
    return null;
  }
  try {
    me = (await api("/users/me")).data;
  } catch { return null; }
  nav.append(
    h("a", { href: `/u/${encodeURIComponent(me.username)}` }, `@${me.username}`),
    h("a", { href: "/account" }, "Account"),
    h("button", { type: "button", onclick: () => { token.clear(); location.href = "/login"; } }, "Log out"),
  );
  return me;
}

async function requireLogin() {
  if (!token.get()) {
    location.href = "/login?next=" + encodeURIComponent(location.pathname + location.search);
    return false;
  }
  return Boolean(await loadNav());
}

// ---------- post rendering (shared by feed, profile and post pages) ----------

function renderPost(item, { detail = false, onDeleted } = {}) {
  const post = item.Post;
  const state = { votes: item.votes, voted: item.voted };

  const voteButton = h("button", { type: "button", "aria-pressed": String(state.voted) });
  const paint = () => {
    voteButton.setAttribute("aria-pressed", String(state.voted));
    voteButton.textContent = `${state.voted ? "♥" : "♡"} ${state.votes}`;
    voteButton.setAttribute("aria-label", `${state.voted ? "Unlike" : "Like"} (${state.votes} likes)`);
  };
  paint();
  voteButton.addEventListener("click", async () => {
    voteButton.disabled = true;
    try {
      await api("/vote/", { method: "POST", json: { post_id: post.id, dir: state.voted ? 0 : 1 } });
      state.voted = !state.voted;
      state.votes += state.voted ? 1 : -1;
      paint();
    } catch (err) { notice(err.message); }
    finally { voteButton.disabled = false; }
  });

  const actions = h("div", { class: "post-actions" }, voteButton,
    h("a", { class: "pill", href: `/post/${post.id}` }, `${item.comments} comment${item.comments === 1 ? "" : "s"}`));

  if (me && me.id === post.owner_id) {
    actions.append(h("button", {
      type: "button", class: "danger",
      onclick: async () => {
        if (!confirm("Delete this post? This cannot be undone.")) return;
        try {
          await api(`/posts/${post.id}`, { method: "DELETE" });
          if (detail) location.href = "/"; else onDeleted && onDeleted(post.id);
        } catch (err) { notice(err.message); }
      },
    }, "Delete"));
  }

  const title = detail ? h("h1", { class: "post-title" }, post.title)
                       : h("h3", { class: "post-title" }, h("a", { href: `/post/${post.id}` }, post.title));
  return h("article", { class: "post", "data-post-id": post.id },
    h("img", { class: "avatar", src: post.owner.image_url, alt: "", loading: "lazy" }),
    h("div", {},
      h("div", { class: "post-head" },
        h("a", { href: `/u/${encodeURIComponent(post.owner.username)}` }, post.owner.username),
        ` · ${formatDate(post.created_at)}`,
        post.published ? null : h("span", { class: "badge" }, "Draft")),
      title,
      h("p", { class: "post-body" }, post.content),
      actions));
}

/** Paged list used by the feed and profile pages. */
function postList({ buildUrl }) {
  const list = $("#posts"), empty = $("#empty"), more = $("#load-more");
  const PAGE = 10;
  let skip = 0;

  async function load(reset) {
    if (reset) { skip = 0; list.replaceChildren(); }
    more.disabled = true;
    try {
      const { data, res } = await api(buildUrl(PAGE, skip));
      for (const item of data) {
        list.append(renderPost(item, {
          onDeleted: (id) => { list.querySelector(`[data-post-id="${id}"]`)?.remove(); empty.hidden = list.children.length > 0; },
        }));
      }
      skip += data.length;
      const total = Number(res.headers.get("X-Total-Count") || 0);
      more.hidden = skip >= total;
      empty.hidden = list.children.length > 0;
    } catch (err) { notice(err.message); }
    finally { more.disabled = false; }
  }
  more.addEventListener("click", () => load(false));
  return { reload: () => load(true) };
}

// ---------- pages ----------

const pages = {
  async feed() {
    if (!(await requireLogin())) return;
    const sort = $("#sort"), search = $("#search");
    const list = postList({
      buildUrl: (limit, skip) =>
        `/posts/?limit=${limit}&skip=${skip}&sort=${sort.value}&search=${encodeURIComponent(search.value.trim())}`,
    });
    let timer;
    search.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(list.reload, 300); });
    sort.addEventListener("change", list.reload);

    const composer = $("#composer");
    onSubmit(composer, async (form) => {
      await api("/posts/", { method: "POST", json: {
        title: form.get("title").trim(), content: form.get("content").trim(), published: form.get("published") === "on",
      }});
      composer.reset();
      composer.querySelector("[name=published]").checked = true;
      notice("Post published.", "success");
      list.reload();
    });
    list.reload();
  },

  async profile() {
    if (!(await requireLogin())) return;
    const box = $("#profile"), username = box.dataset.username;
    try {
      const { data: user } = await api(`/users/${encodeURIComponent(username)}`);
      document.title = `${user.username} · ${document.title.split("·").pop().trim()}`;
      box.append(h("div", { class: "profile-head" },
        h("img", { class: "avatar large", src: user.image_url, alt: `${user.username}'s profile picture` }),
        h("div", {},
          h("h1", {}, `@${user.username}`),
          user.bio ? h("p", {}, user.bio) : null,
          h("p", { class: "muted" }, `Joined ${new Date(user.created_at).toLocaleDateString(undefined, { dateStyle: "medium" })} · ${user.posts_count} post${user.posts_count === 1 ? "" : "s"}`),
          me && me.id === user.id ? h("a", { href: "/account" }, "Edit profile") : null)));
    } catch (err) { box.append(h("p", { class: "notice error" }, err.message)); return; }
    postList({
      buildUrl: (limit, skip) => `/posts/?limit=${limit}&skip=${skip}&owner=${encodeURIComponent(username)}`,
    }).reload();
  },

  async post() {
    if (!(await requireLogin())) return;
    const postId = $("#post").dataset.postId;
    const commentsBox = $("#comments");

    async function loadPost() {
      try {
        const { data } = await api(`/posts/${postId}`);
        $("#post").replaceChildren(renderPost(data, { detail: true }));
        document.title = `${data.Post.title} · ${document.title.split("·").pop().trim()}`;
      } catch (err) { $("#post").replaceChildren(h("p", { class: "notice error" }, err.message)); $("#comment-form").hidden = true; }
    }

    function renderComment(c) {
      const canDelete = me && (me.id === c.author.id || me.id === postOwnerId);
      return h("article", { class: "comment" },
        h("img", { class: "avatar", src: c.author.image_url, alt: "" }),
        h("div", {},
          h("div", { class: "post-head" }, h("a", { href: `/u/${encodeURIComponent(c.author.username)}` }, c.author.username), ` · ${formatDate(c.created_at)}`),
          h("p", {}, c.content),
          canDelete ? h("button", { type: "button", class: "danger", onclick: async () => {
            if (!confirm("Delete this comment?")) return;
            try { await api(`/comments/${c.id}`, { method: "DELETE" }); loadComments(); loadPost(); }
            catch (err) { notice(err.message); }
          }}, "Delete") : null));
    }

    let postOwnerId = null;
    async function loadComments() {
      try {
        const { data } = await api(`/posts/${postId}/comments`);
        commentsBox.replaceChildren(...data.map(renderComment));
        if (!data.length) commentsBox.append(h("p", { class: "muted" }, "No comments yet."));
      } catch (err) { notice(err.message); }
    }

    try { postOwnerId = (await api(`/posts/${postId}`)).data.Post.owner_id; } catch { /* loadPost shows the error */ }
    await loadPost();
    if (postOwnerId !== null) await loadComments();

    const form = $("#comment-form");
    onSubmit(form, async (data) => {
      await api(`/posts/${postId}/comments`, { method: "POST", json: { content: data.get("content").trim() } });
      form.reset();
      await Promise.all([loadComments(), loadPost()]);
    });
  },

  async account() {
    if (!(await requireLogin())) return;
    const avatar = $("#avatar");
    const fill = (user) => {
      me = user;
      avatar.src = user.image_url;
      $("#username").value = user.username;
      $("#bio").value = user.bio || "";
      $("#email").textContent = user.email;
    };
    fill(me);

    onSubmit($("#profile-form"), async (form) => {
      fill((await api("/users/me", { method: "PATCH", json: { username: form.get("username").trim(), bio: form.get("bio").trim() } })).data);
      await loadNav();
      notice("Profile saved.", "success");
    });

    onSubmit($("#picture-form"), async (form) => {
      const file = form.get("file");
      if (file && file.size > 5 * 1024 * 1024) throw new Error("Image must be smaller than 5 MB");
      fill((await api("/users/me/picture", { method: "POST", body: form })).data);
      $("#picture-form").reset();
      notice("Profile picture updated.", "success");
    });

    $("#remove-picture").addEventListener("click", async () => {
      clearNotice();
      try { fill((await api("/users/me/picture", { method: "DELETE" })).data); notice("Profile picture removed.", "success"); }
      catch (err) { notice(err.message); }
    });

    const pwForm = $("#password-form");
    onSubmit(pwForm, async (form) => {
      await api("/users/me/password", { method: "POST", json: { current_password: form.get("current_password"), new_password: form.get("new_password") } });
      pwForm.reset();
      notice("Password changed.", "success");
    });
  },

  async login() {
    await loadNav();
    if (me) { location.href = safeNext(); return; }
    onSubmit($("#login-form"), async (form) => {
      // The login endpoint expects form-encoded data (OAuth2 standard), not JSON.
      const body = new URLSearchParams({ username: form.get("username").trim(), password: form.get("password") });
      const { data } = await api("/login", { method: "POST", body, auth: false });
      token.set(data.access_token);
      location.href = safeNext();
    });
  },

  async register() {
    await loadNav();
    onSubmit($("#register-form"), async (form) => {
      await api("/users/", { method: "POST", auth: false, json: {
        email: form.get("email").trim(), username: form.get("username").trim(), password: form.get("password"),
      }});
      const body = new URLSearchParams({ username: form.get("email").trim(), password: form.get("password") });
      const { data } = await api("/login", { method: "POST", body, auth: false });
      token.set(data.access_token);
      location.href = "/";
    });
  },

  async forgot() {
    await loadNav();
    onSubmit($("#forgot-form"), async (form) => {
      const { data } = await api("/forgot-password", { method: "POST", auth: false, json: { email: form.get("email").trim() } });
      notice(data.detail, "success");
    });
  },

  async reset() {
    await loadNav();
    const resetToken = new URLSearchParams(location.search).get("token");
    if (!resetToken) { notice("This reset link is incomplete. Request a new one."); $("#reset-form").hidden = true; return; }
    onSubmit($("#reset-form"), async (form) => {
      const { data } = await api("/reset-password", { method: "POST", auth: false, json: { token: resetToken, new_password: form.get("new_password") } });
      notice(data.detail, "success");
      setTimeout(() => { location.href = "/login"; }, 1500);
    });
  },
};

document.addEventListener("DOMContentLoaded", () => {
  const init = pages[document.body.dataset.page];
  if (init) init();
});
