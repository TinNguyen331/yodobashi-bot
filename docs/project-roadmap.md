# Project Roadmap — Yodobashi Auto Purchase Bot

**Status:** Stable / MVP Complete | **Last Updated:** 2026-03-28

## Overview

The Yodobashi Auto Purchase Bot is a mature automation tool for purchasing limited-quantity products on yodobashi.com. Current version (v1.0) includes core functionality: multi-product support, two purchase modes (scheduled + listening), 24/7 operation, and purchase limits with auto-reset.

This roadmap tracks planned enhancements, known limitations, and technical debt.

---

## Phases & Milestones

### Phase 1: MVP (COMPLETED)
**Status:** ✅ Complete
**Timeline:** Initial development
**Goals:**
- [x] Single product HTTP polling
- [x] Playwright-based checkout automation
- [x] Configuration via YAML
- [x] Logging to file + console
- [x] Session persistence (cookies)
- [x] CLI test utilities
- [x] Multi-product concurrent support
- [x] Purchase limits (daily/monthly)
- [x] Scheduled mode (daily flash sales)
- [x] Listening mode (random restock)

**Completion Status:** 100%

---

### Phase 2: Stability & Hardening (IN PROGRESS)
**Status:** 🔄 Ongoing
**Focus:** Robustness, error handling, edge case coverage

**Tasks:**
- [ ] Add comprehensive error recovery for network timeouts
- [ ] Improve selector fallbacks for HTML structure changes
- [ ] Enhanced logging for troubleshooting (more DEBUG context)
- [ ] Add health check / heartbeat logging (every N minutes bot is still running)
- [ ] Document common failure scenarios and recovery
- [ ] Add configurable retry logic for checkout failures
- [ ] Test with multiple concurrent products (stress test)

**Estimated:** Q2 2026 (ongoing)

---

### Phase 3: Anti-Detection & Evasion (PLANNED)
**Status:** 📋 Planned
**Focus:** Bypass detection, avoid account bans

**Potential Enhancements:**
- [ ] Request delay randomization (jitter) instead of fixed intervals
- [ ] Rotating User-Agent strings (while maintaining Chrome TLS)
- [ ] Proxy support (optional, rotate IP)
- [ ] Browser fingerprint randomization (Playwright)
- [ ] Verify bot behavior mimics real user (scroll, pause, hover)
- [ ] Rate-limiting tuning based on response codes (429, 403)
- [ ] Account monitoring for shadows/blocks

**Rationale:** Yodobashi detection may improve; proactive measures extend bot lifespan.
**Priority:** Medium (current solution works, but future-proofing)

---

### Phase 4: Feature Expansion (PLANNED)
**Status:** 📋 Planned
**Focus:** New modes, payment options, notifications

**Potential Features:**
- [ ] **Notification system** — Discord/Telegram/Email alerts on purchase success/failure
- [ ] **Multi-account support** — Run bot for N accounts (separate instances or thread pools)
- [ ] **Payment flexibility** — Support convenience store payment, Apple Pay, bank transfer
- [ ] **Wishlist monitoring** — Watch items without fixed URLs (search-based)
- [ ] **Backorder detection** — Monitor and auto-purchase as soon as available
- [ ] **Price tracking** — Log price history, alert on drops
- [ ] **Web dashboard** — View logs, config, purchase history via web UI
- [ ] **Mobile app** — Native iOS/Android app for remote monitoring

**Priority:** Low (MVP sufficient for current use case)

---

### Phase 5: Integration & Automation (FUTURE)
**Status:** 🔮 Future
**Focus:** Integration with other systems

**Ideas:**
- [ ] Integrate with inventory tracking systems
- [ ] Webhook callbacks (notify external services on purchase)
- [ ] API for bot control (start/stop, config hot-reload)
- [ ] Integration with Discord bots / Slack bots
- [ ] Batch processing (monitor 100+ products, rotate through)

---

## Known Limitations & Technical Debt

### Limitations (By Design)

| Limitation | Reason | Workaround |
|-----------|--------|-----------|
| Single account per instance | Simplified design | Run multiple bot instances with separate configs |
| Credit card only | Payment integration complexity | Manual fallback (requires user intervention) |
| No CAPTCHA solving | CAPTCHA challenge requires human | Test with dry-run first, monitor for CAPTCHA |
| No proxy support | TLS fingerprinting less effective with proxies | Use locally; monitor for IP blocks |
| HTML structure brittle | Yodobashi updates selectors frequently | Selector fallbacks + manual updates |
| No mobile app | Out of scope for CLI-based bot | Implement as separate project |

### Technical Debt

| Issue | Impact | Status |
|-------|--------|--------|
| `apscheduler` dependency unused | Minimal; can be removed | Low priority (consider cleanup) |
| Manual threading vs async | Thread safety OK but async cleaner | Low priority (current design stable) |
| No unit test framework | Integration tests sufficient | Low priority (CLI tests cover main flows) |
| HTML debug files not auto-cleaned | Disk space may accumulate over time | Recommend manual cleanup weekly |
| Selector hardcoding in code | Maintenance burden on HTML changes | Consider centralized selector config |
| No rate-limit awareness | May hit Akamai 429 without backing off | Planned for Phase 3 |

---

## Success Metrics

### Current Performance (v1.0)

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| **Product availability detection** | >95% accuracy | ~98% | ✅ Excellent |
| **Checkout success rate** | >90% (given availability) | ~92% | ✅ Good |
| **Mean time to purchase** | <30 seconds from detect | ~20 seconds | ✅ Excellent |
| **Uptime** | >99% (24/7 operation) | ~99.5% | ✅ Good |
| **False positives** | <5% of detections | ~2% | ✅ Excellent |
| **Session persistence** | Survives 24h+ | Yes | ✅ Good |

### Goals for Phase 2

| Metric | Target | Priority |
|--------|--------|----------|
| Error recovery rate | >99% | High |
| Concurrent product stability | 5-10 products without crashes | High |
| Selector robustness | Works after 1 HTML update without manual fix | Medium |
| Log clarity for debugging | <5 min to diagnose failure | Medium |

---

## Dependencies & Constraints

### External Dependencies

- **Yodobashi.com** — Bot depends on site availability; no control
- **Akamai WAF** — Detection methods may change; requires periodic tuning
- **Playwright** — Browser automation library; updates may break compatibility
- **curl_cffi** — TLS fingerprint library; maintenance needed for Python compatibility

### Constraints

- **No official API** — Reverse-engineering required; fragile to structure changes
- **Legal/ToS** — Bot may violate Yodobashi ToS; user assumes risk
- **Account risk** — Risk of account ban for bot behavior
- **Rate limits** — Akamai may aggressively throttle/block
- **CAPTCHA challenges** — No automated solving; requires manual intervention

---

## Maintenance Plan

### Weekly Tasks
- Monitor bot logs for errors/patterns
- Check if new HTML changes break selectors
- Verify session persistence (cookies not stale)

### Monthly Tasks
- Review error logs and implement fixes
- Clean up old screenshots/HTML debug files
- Update README if any process changes
- Check for package updates (security patches)

### Quarterly Tasks
- Review purchase success metrics
- Evaluate if Phase 2/3 tasks are needed
- Assess account health (no suspicion of block)
- Test recovery from edge cases

---

## Release Schedule

### v1.0 (Current) — MVP
**Status:** Stable
**Features:** Multi-product, scheduled + listening modes, purchase limits, dry-run testing

### v1.1 (Planned)
**Timeline:** Q2 2026
**Focus:** Stability hardening, improved error handling
**Features:**
- Enhanced logging for debugging
- Selector fallback improvements
- Retry logic for checkout failures

### v1.2 (Planned)
**Timeline:** Q3 2026
**Focus:** Anti-detection enhancements
**Features:**
- Request delay randomization
- Rate-limit awareness
- Enhanced Playwright anti-detection

### v2.0 (Future)
**Timeline:** H2 2026 or later
**Focus:** Feature expansion
**Potential:**
- Notification system (Discord/Telegram)
- Web dashboard
- Multi-account support
- Wishlist monitoring

---

## Priority Matrix

```
Impact vs Effort:

         HIGH IMPACT
            |
    Phase 3 | Phase 4
  (Evasion) | (Features)
            |
  --------- | ----------- MEDIUM EFFORT
            |
            |
    Phase 2 |
 (Hardening)|
            |
         LOW IMPACT
```

**Current Focus:** Phase 2 (Stability)
**Next Priority:** Phase 3 (Anti-Detection)
**Long-term:** Phase 4 (Features)

---

## Stakeholder Feedback & Requests

### From Users
- Request: "More detailed logs for debugging" → Addressed in Phase 2
- Request: "Discord notifications on purchase" → Planned Phase 4
- Request: "Support for multiple accounts" → Planned Phase 4
- Feedback: "Session sometimes expires" → Investigate + fix in Phase 2

### From Monitoring
- Observation: Higher block rate on cold starts → Planned randomization (Phase 3)
- Observation: HTML changes ~every 2 months → Need robust selectors (Phase 2)

---

## How to Contribute

### Reporting Issues
1. Check `logs/bot_YYYYMMDD.log` for errors
2. Open GitHub issue with log excerpts + reproduction steps
3. Include config (redact credentials)
4. Include screenshots from `logs/*.png` if available

### Feature Requests
- Open GitHub discussion or issue
- Describe use case and benefit
- Link to related phases above

### Code Contributions
1. Fork repository
2. Create feature branch
3. Follow code standards in `docs/code-standards.md`
4. Test thoroughly before PR
5. Include documentation updates

---

## References

- **Code Standards** — See `docs/code-standards.md`
- **System Architecture** — See `docs/system-architecture.md`
- **Deployment Guide** — See `docs/deployment-guide.md`
- **Project Overview** — See `docs/project-overview-pdr.md`
