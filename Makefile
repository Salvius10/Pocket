# Every target delegates to scripts/tasks.py so Windows (make.ps1) and macOS/Linux behave the same.
TARGETS := setup dev migrate seed-demo funds sms-variants lint typecheck test l10n \
           eval-parsers eval-insights eval-composer eval-chats app apk web serve-web

.PHONY: $(TARGETS)
$(TARGETS):
	uv run python scripts/tasks.py $@
