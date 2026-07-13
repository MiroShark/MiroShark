<template>
  <!-- Site-wide footer — ported 1:1 from miroshark.xyz so every page shares
       the same links + credit line. -->
  <footer class="site-footer">
    <div class="metal-rule"></div>
    <nav class="site-footer-nav">
      <a href="https://miroshark.xyz/docs" target="_blank" rel="noopener noreferrer">Docs</a>
      <span class="site-footer-sep" aria-hidden="true">·</span>
      <a href="https://github.com/MiroShark/MiroShark" target="_blank" rel="noopener noreferrer">GitHub</a>
      <span class="site-footer-sep" aria-hidden="true">·</span>
      <a href="https://x.com/miroshark_" target="_blank" rel="noopener noreferrer">X</a>
      <span class="site-footer-sep" aria-hidden="true">·</span>
      <a href="https://bankr.bot/discover/0xd7bc6a05a56655fb2052f742b012d1dfd66e1ba3" target="_blank" rel="noopener noreferrer">Bankr</a>
    </nav>
    <p class="site-footer-copy">
      © {{ year }} MiroShark · Built by
      <a href="https://x.com/aaronjmars" target="_blank" rel="noopener noreferrer" class="site-footer-author">Aaron Elijah Mars</a>
    </p>
  </footer>
</template>

<script setup>
const year = new Date().getFullYear()
</script>

<style scoped>
.site-footer {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
  width: 100%;
  max-width: 42rem;
  margin: 6rem auto 0;
  padding: 0 1.5rem 3rem;
  color: rgba(228, 222, 255, 0.8);
  font-family: var(--font-sans);
}

.site-footer-nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0.5rem 1.25rem;
  font-size: 0.875rem;
}

.site-footer-nav a {
  color: inherit;
  text-decoration: none;
  transition: color 160ms ease;
}

.site-footer-nav a:hover {
  color: #ffffff;
}

.site-footer-sep {
  opacity: 0.4;
}

.site-footer-copy {
  font-size: 0.75rem;
  letter-spacing: 0.01em;
  color: rgba(228, 222, 255, 0.6);
  text-align: center;
}

.site-footer-author {
  color: inherit;
  text-underline-offset: 2px;
  text-decoration: none;
}

.site-footer-author:hover {
  color: #ffffff;
  text-decoration: underline;
}
</style>
