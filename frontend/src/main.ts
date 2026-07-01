import './app.css'
import App from './App.svelte'
import { mount } from 'svelte'
import { registerSW } from 'virtual:pwa-register'

// Silently fetch a new service worker in the background and reload once it
// takes control, so reopening the (installed) app never gets stuck on a
// stale shell from a previous deploy — critical on iOS, where a PWA is
// rarely "fully closed" and its disk cache is very sticky.
const updateSW = registerSW({
  immediate: true,
  onNeedRefresh() {
    updateSW(true)
  },
})

const app = mount(App, { target: document.getElementById('app')! })

export default app
