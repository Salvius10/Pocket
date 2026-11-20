import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/json.dart';
import '../../core/state.dart';
import '../../core/theme.dart';
import '../../core/ui.dart';
import '../../l10n/app_localizations.dart';

/// Monthly report: one complete month's money in, money out and what changed.
///
/// Every figure, every percentage, every bar length and every sentence comes from core-api
/// (`GET /v1/reports/monthly`). This screen only lays them out.
class ReportScreen extends ConsumerStatefulWidget {
  const ReportScreen({super.key});

  @override
  ConsumerState<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends ConsumerState<ReportScreen> {
  String? _month;
  Json? _last; // the report on screen while another month loads

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final path = _month == null ? '/v1/reports/monthly' : '/v1/reports/monthly?month=$_month';
    final result = ref.watch(fetchProvider(path));
    final fresh = result.value;
    if (fresh != null) _last = fresh;
    final report = fresh ?? _last;
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(Pk.pad, 8, Pk.pad, 40),
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: IconButton(
                onPressed: () => context.pop(),
                icon: const Icon(Icons.arrow_back, color: Pk.bone),
                tooltip: MaterialLocalizations.of(context).backButtonTooltip,
              ),
            ),
            Text(l.reportTitle.toUpperCase(), style: Pk.label(c: Pk.faint)),
            const SizedBox(height: 4),
            if (report != null)
              ReportBody(report: report, loading: fresh == null && !result.hasError, onMonth: (m) => setState(() => _month = m))
            else if (result.hasError)
              Padding(
                padding: const EdgeInsets.only(top: 60),
                child: StateNote(
                  icon: Icons.cloud_off_outlined,
                  title: l.errorTitle,
                  body: l.errorBody,
                  action: l.retry,
                  onAction: () => ref.invalidate(fetchProvider(path)),
                ),
              )
            else ...const [SizedBox(height: 44), Skeleton(height: 120), SizedBox(height: Pk.gap), Skeleton(height: 210), SizedBox(height: Pk.gap), Skeleton(height: 160)],
          ],
        ),
      ),
    );
  }
}

/// The report itself, from one server answer.
class ReportBody extends StatelessWidget {
  const ReportBody({super.key, required this.report, required this.onMonth, this.loading = false});
  final Json report;
  final ValueChanged<String> onMonth;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final r = report;
    final months = r.l('months');
    final positive = r['net_is_positive'] != false;
    final spentPct = r['spend_pct_of_income'];
    final direction = r.s('spend_direction');
    final categories = r.l('categories');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(r.s('month_label'), style: Pk.text(30, w: FontWeight.w600, h: 1.1, ls: -0.6)),
        if (months.isNotEmpty) ...[
          const SizedBox(height: 14),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final m in months)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: PChip(label: m.s('label'), selected: m.s('month') == r.s('month'), onTap: () => onMonth(m.s('month'))),
                  ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 16),
        AnimatedOpacity(
          opacity: loading ? 0.45 : 1,
          duration: const Duration(milliseconds: 160),
          child: Column(
            key: ValueKey(r.s('month')),
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (months.isEmpty && r.paise('spend') == 0 && r.paise('income') == 0)
                Padding(padding: const EdgeInsets.only(top: 40), child: StateNote(title: l.reportNone))
              else ...[
                Rise(
                  index: 0,
                  child: PCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SectionLabel(l.reportInShort, index: 1, color: Pk.lime),
                        const SizedBox(height: 12),
                        for (final (i, line) in r.strings('lines').indexed)
                          Padding(
                            padding: EdgeInsets.only(top: i == 0 ? 0 : 6),
                            child: Text(line, style: i == 0 ? Pk.text(17, w: FontWeight.w500, h: 1.4) : Pk.text(14.5, c: Pk.muted, h: 1.45)),
                          ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: Pk.gap),
                Rise(
                  index: 1,
                  child: PCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SectionLabel(l.reportMonthWent, index: 2),
                        const SizedBox(height: 16),
                        Text((positive ? l.reportLeftOver : l.reportOverspent).toUpperCase(), style: Pk.label(c: Pk.faint, size: 10)),
                        const SizedBox(height: 4),
                        FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerLeft,
                          child: Text(r.money('net_abs'), style: Pk.num(40, w: FontWeight.w600, c: positive ? Pk.lime : Pk.coral, ls: -1)),
                        ),
                        if (spentPct is int) ...[
                          const SizedBox(height: 14),
                          SegBar(pct: spentPct, color: positive ? Pk.lime : Pk.coral, segments: 32, height: 12),
                          const SizedBox(height: 8),
                          Text(l.reportSpentOfIncome(spentPct), style: Pk.text(13, c: Pk.muted)),
                        ],
                        const Stitch(vertical: 16),
                        Row(
                          children: [
                            Expanded(child: _Figure(l.reportCameIn, r.money('income'))),
                            Expanded(child: _Figure(l.stsSpent, r.money('spend'))),
                            Expanded(child: _Figure(l.reportSaved, r.money('saved'))),
                          ],
                        ),
                        const SizedBox(height: 14),
                        Row(
                          children: [
                            Expanded(child: _Figure(l.stsCommitted, r.money('committed'))),
                            Expanded(flex: 2, child: _Figure(l.reportOther, r.money('flexible'))),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                if (r['has_previous'] == true) ...[
                  const SizedBox(height: Pk.gap),
                  Rise(
                    index: 2,
                    child: PCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SectionLabel(l.reportAgainst(r.s('previous_label')), index: 3),
                          const SizedBox(height: 14),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              Tag(
                                switch (direction) { 'down' => l.reportLess(r.money('spend_delta')), 'up' => l.reportMore(r.money('spend_delta')), _ => l.reportSame },
                                color: switch (direction) { 'down' => Pk.lime, 'up' => Pk.coral, _ => Pk.muted },
                              ),
                              if (r['spend_delta_pct'] is int && direction != 'same') Tag('${r['spend_delta_pct']}%'),
                            ],
                          ),
                          const SizedBox(height: 16),
                          _MonthBar(label: r.s('month_label').split(' ').first, amount: r.money('spend'), pct: r.m('bars').i('month'), strong: true),
                          const SizedBox(height: 12),
                          _MonthBar(label: r.s('previous_label'), amount: r.money('previous_spend'), pct: r.m('bars').i('previous')),
                        ],
                      ),
                    ),
                  ),
                ],
                if (categories.isNotEmpty) ...[
                  const SizedBox(height: Pk.gap),
                  Rise(
                    index: 3,
                    child: PCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SectionLabel(l.wSpend, index: r['has_previous'] == true ? 4 : 3),
                          const SizedBox(height: 6),
                          for (final (i, c) in categories.indexed) _CategoryRow(c, top: i == 0),
                        ],
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 18),
                Center(child: Text(l.reportFootnote, textAlign: TextAlign.center, style: Pk.text(12.5, c: Pk.faint, h: 1.4))),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _Figure extends StatelessWidget {
  const _Figure(this.label, this.value);
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label.toUpperCase(), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.label(c: Pk.faint, size: 10)),
        const SizedBox(height: 4),
        FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text(value, style: Pk.num(15, w: FontWeight.w600))),
      ],
    );
  }
}

class _MonthBar extends StatelessWidget {
  const _MonthBar({required this.label, required this.amount, required this.pct, this.strong = false});
  final String label;
  final String amount;
  final int pct;
  final bool strong;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(14, c: strong ? Pk.bone : Pk.muted, w: strong ? FontWeight.w600 : FontWeight.w400))),
            Text(amount, style: Pk.num(14, c: strong ? Pk.bone : Pk.muted)),
          ],
        ),
        const SizedBox(height: 6),
        SegBar(pct: pct, color: strong ? Pk.bone : Pk.lineStrong, segments: 32, height: 8),
      ],
    );
  }
}

class _CategoryRow extends StatelessWidget {
  const _CategoryRow(this.c, {this.top = false});
  final Json c;
  final bool top;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          EmojiTile(c.s('emoji', '•'), size: 32),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(child: Text(c.s('name'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(14.5, w: FontWeight.w500))),
                    Text('${c.i('pct')}%', style: Pk.num(12, c: Pk.faint)),
                    const SizedBox(width: 12),
                    Text(c.money('amount'), style: Pk.num(14)),
                  ],
                ),
                const SizedBox(height: 7),
                SegBar(pct: c.i('pct'), color: top ? Pk.lime : Pk.sage, segments: 32, height: 6),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
