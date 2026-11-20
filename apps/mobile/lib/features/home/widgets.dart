import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/json.dart';
import '../../core/state.dart';
import '../../core/theme.dart';
import '../../core/ui.dart';
import '../../l10n/app_localizations.dart';

/// The 12 catalog widgets. Each reads its numbers from the local cache (the last sync bundle)
/// and never computes a total. The same widgets are used by both Home renderers.
const catalog = [
  'safe_to_spend', 'pockets', 'goals', 'spend_by_category', 'cash_flow', 'transactions',
  'bills_emis', 'net_worth', 'investments', 'insight_card', 'pulse_card', 'group_pot',
];

String widgetTitle(L l, String type) => switch (type) {
      'safe_to_spend' => l.safeToSpend,
      'pockets' => l.wPockets,
      'goals' => l.wGoals,
      'spend_by_category' => l.wSpend,
      'cash_flow' => l.wCashFlow,
      'transactions' => l.wTransactions,
      'bills_emis' => l.wBills,
      'net_worth' => l.wNetWorth,
      'investments' => l.wInvestments,
      'insight_card' => l.wInsight,
      'pulse_card' => l.wPulse,
      'group_pot' => l.wGroup,
      _ => type,
    };

String statusLabel(L l, String status) => switch (status) {
      'over' => l.statusOver,
      'watch' => l.statusWatch,
      'behind' => l.statusBehind,
      'reached' => l.statusReached,
      'paused' => l.statusPaused,
      _ => l.statusOk,
    };

/// Builds one catalog widget. Returns null for an unknown type: Home never draws one.
Widget? buildCatalogWidget(String type, {required Json params, required String variant, required int index}) {
  if (!catalog.contains(type)) return null;
  return _CatalogWidget(type: type, params: params, variant: variant, index: index);
}

class _CatalogWidget extends ConsumerWidget {
  const _CatalogWidget({required this.type, required this.params, required this.variant, required this.index});
  final String type;
  final Json params;
  final String variant;
  final int index;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = ref.watch(appProvider);
    final l = L.of(context);
    final s = app.summary;
    void tab(int i) => ref.read(tabProvider.notifier).go(i);
    switch (type) {
      case 'safe_to_spend':
        return SafeToSpendHero(sts: s.m('safe_to_spend'), index: index);
      case 'pockets':
        final items = _sorted(s.l('pockets'), params.s('sort'));
        return _Frame(index: index, title: l.wPockets, onTap: () => tab(3), child: PocketRows(items: items.take(params.i('max_items', 4)).toList()));
      case 'goals':
        return _Frame(index: index, title: l.wGoals, onTap: () => tab(3), child: GoalRows(items: s.l('goals').take(params.i('max_items', 3)).toList()));
      case 'spend_by_category':
        return _Frame(index: index, title: l.wSpend, trailing: l.thisMonth, onTap: () => tab(1), child: SpendByCategory(data: s.m('spend_by_category'), topN: params.i('top_n', 5)));
      case 'cash_flow':
        return _Frame(index: index, title: l.wCashFlow, child: CashFlowChart(data: s.m('cash_flow'), weeks: params.s('span') == 'weeks'));
      case 'transactions':
        return _Frame(index: index, title: l.wTransactions, onTap: () => tab(1), child: TxnRows(items: app.transactions.take(params.i('max_items', 5)).toList()));
      case 'bills_emis':
        final all = s.m('bills').l('upcoming');
        final window = params.i('window_days', 14);
        final items = all.where((b) => b.i('days_until') <= window).take(variant == 'compact' ? 3 : 5).toList();
        return _Frame(index: index, title: l.wBills, onTap: () => tab(1), child: BillRows(items: items));
      case 'net_worth':
        return _Frame(index: index, title: l.wNetWorth, child: NetWorthBlock(data: s.m('net_worth')));
      case 'investments':
        return _Frame(index: index, title: l.wInvestments, onTap: () => tab(1), child: InvestmentsBlock(data: s.m('investments'), maxItems: params.i('max_items', 3)));
      case 'insight_card':
        // Lead with the one the user can act on (it carries a confirm card); otherwise the most serious.
        final first = app.insights.where((i) => i['proposal'] is Map).firstOrNull ?? app.insights.firstOrNull;
        return _Frame(
          index: index,
          title: l.wInsight,
          accent: first == null ? null : Pk.statusColor(first.i('severity') >= 3 ? 'over' : first.i('severity') == 2 ? 'watch' : null),
          onTap: () => tab(2),
          child: first == null ? _Quiet(l.noInsights) : InsightBody(insight: first),
        );
      case 'pulse_card':
        final items = app.pulse.l('items');
        return _Frame(index: index, title: l.wPulse, onTap: () => tab(2), child: items.isEmpty ? _Quiet(l.pulseEmpty) : PulseBody(item: items.first));
      case 'group_pot':
        final gid = params.sn('group_id');
        final group = app.groups.where((g) => gid == null || g.s('id') == gid).firstOrNull ?? app.groups.firstOrNull;
        return _Frame(
          index: index,
          title: group == null ? l.wGroup : group.s('name'),
          onTap: group == null ? () => tab(4) : () => context.push('/group/${group.s('id')}'),
          child: group == null ? _Quiet(l.noGroups) : GroupPotBlock(group: group),
        );
    }
    return const SizedBox.shrink();
  }

  List<Json> _sorted(List<Json> pockets, String sort) {
    final list = [...pockets];
    if (sort == 'risk') list.sort((a, b) => b.i('pct').compareTo(a.i('pct')));
    return list;
  }
}

class _Quiet extends StatelessWidget {
  const _Quiet(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Text(text, style: Pk.text(14, c: Pk.muted)));
}

/// Card chrome shared by every widget: numbered label, optional accent edge.
class _Frame extends StatelessWidget {
  const _Frame({required this.index, required this.title, required this.child, this.onTap, this.trailing, this.accent});
  final int index;
  final String title;
  final Widget child;
  final VoidCallback? onTap;
  final String? trailing;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    return PCard(
      onTap: onTap,
      border: accent?.withValues(alpha: 0.55) ?? Pk.line,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionLabel(
            title,
            index: index + 1,
            color: accent ?? Pk.muted,
            trailing: trailing != null ? Text(trailing!.toUpperCase(), style: Pk.label(c: Pk.faint, size: 10)) : (onTap != null ? const Icon(Icons.arrow_outward, size: 14, color: Pk.faint) : null),
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

// ---------- 1. Safe to spend ----------
class SafeToSpendHero extends StatelessWidget {
  const SafeToSpendHero({super.key, required this.sts, this.index = 0});
  final Json sts;
  final int index;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final status = sts.s('status', 'ok');
    final over = status == 'over';
    final empty = status == 'empty';
    final color = over ? Pk.coral : empty ? Pk.amber : Pk.lime;
    final big = sts.m(over ? 'left_today' : 'left_today').s('display', '—');
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: Pk.surface,
        borderRadius: BorderRadius.circular(Pk.r),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(Pk.pad, Pk.pad, Pk.pad, 0),
            child: SectionLabel(l.safeToSpend, index: index + 1, color: color, trailing: Tag(l.daysLeft(sts.i('days_left')), color: Pk.muted)),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(Pk.pad, 10, Pk.pad, 0),
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(big, style: Pk.num(62, w: FontWeight.w500, c: color, h: 1.05, ls: -2)),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(Pk.pad, 4, Pk.pad, 14),
            child: Text(
              empty
                  ? l.nothingLeft
                  : over
                      ? l.overToday(sts.m('left_today').s('display').replaceFirst('-', ''))
                      : '${sts.money('daily')} ${l.perDay}  ·  ${l.spentToday} ${sts.money('spent_today')}',
              style: Pk.text(14.5, c: over || empty ? color : Pk.muted, h: 1.35),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: Pk.pad),
            child: SizedBox(height: 22, width: double.infinity, child: CustomPaint(painter: _MonthTicks(sts.i('day_of_month', 1), sts.i('days_in_month', 30), color))),
          ),
          const Padding(padding: EdgeInsets.symmetric(horizontal: Pk.pad), child: Stitch(vertical: 12)),
          Padding(
            padding: const EdgeInsets.fromLTRB(Pk.pad, 0, Pk.pad, Pk.pad),
            child: Row(
              children: [
                _Mini(l.stsIncome, sts.money('income')),
                _Mini(l.stsCommitted, sts.money('committed')),
                _Mini(l.stsGoals, sts.money('goal_reserve')),
                _Mini(l.stsSpent, sts.money('flexible_spent')),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Mini extends StatelessWidget {
  const _Mini(this.label, this.value);
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label.toUpperCase(), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.label(c: Pk.faint, size: 9.5)),
          const SizedBox(height: 4),
          FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text(value, style: Pk.num(13.5, c: Pk.bone))),
        ],
      ),
    );
  }
}

/// One tick per day of the month: where today sits in it.
class _MonthTicks extends CustomPainter {
  _MonthTicks(this.day, this.days, this.color);
  final int day;
  final int days;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    const gap = 3.0;
    final w = (size.width - gap * (days - 1)) / days;
    for (var i = 0; i < days; i++) {
      final x = i * (w + gap);
      final today = i == day - 1;
      final past = i < day - 1;
      final h = today ? size.height : size.height * 0.55;
      final paint = Paint()..color = today ? color : past ? Pk.lineStrong : Pk.line;
      canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(x, size.height - h, w, h), const Radius.circular(1)), paint);
    }
  }

  @override
  bool shouldRepaint(_MonthTicks old) => old.day != day || old.days != days || old.color != color;
}

// ---------- 2. Pockets ----------
class PocketRows extends StatelessWidget {
  const PocketRows({super.key, required this.items, this.onTapItem});
  final List<Json> items;
  final void Function(Json pocket)? onTapItem;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    if (items.isEmpty) return _Quiet(l.noPockets);
    return Column(
      children: [
        for (final (i, p) in items.indexed) ...[
          if (i > 0) const SizedBox(height: 14),
          Pressable(
            onTap: onTapItem == null ? null : () => onTapItem!(p),
            scale: 0.99,
            child: _PocketRow(p: p, l: l),
          ),
        ],
      ],
    );
  }
}

class _PocketRow extends StatelessWidget {
  const _PocketRow({required this.p, required this.l});
  final Json p;
  final L l;

  @override
  Widget build(BuildContext context) {
    final status = p.s('status', 'ok');
    final color = status == 'ok' ? Pk.lime : status == 'paused' ? Pk.faint : Pk.statusColor(status);
    final left = p.paise('left');
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        EmojiTile(p.s('emoji')),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: Text(p.s('name'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(15.5, w: FontWeight.w500))),
                  if (status != 'ok') Tag(statusLabel(l, status), color: color),
                ],
              ),
              const SizedBox(height: 3),
              Text.rich(
                TextSpan(children: [
                  TextSpan(text: p.money('spent'), style: Pk.num(13.5, c: Pk.bone)),
                  TextSpan(text: '  ${l.ofLimit(p.money('limit'))}', style: Pk.num(12.5, c: Pk.faint, w: FontWeight.w400)),
                  TextSpan(
                    text: '   ${left >= 0 ? l.leftLabel(p.money('left')) : l.overLabel(p.money('left').replaceFirst('-', ''))}',
                    style: Pk.num(12.5, c: left >= 0 ? Pk.muted : Pk.coral, w: FontWeight.w400),
                  ),
                ]),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 8),
              SegBar(pct: p.i('pct'), color: color, height: 8),
            ],
          ),
        ),
      ],
    );
  }
}

// ---------- 3. Goals ----------
class GoalRows extends StatelessWidget {
  const GoalRows({super.key, required this.items});
  final List<Json> items;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    if (items.isEmpty) return _Quiet(l.noGoals);
    return Column(
      children: [
        for (final (i, g) in items.indexed) ...[
          if (i > 0) const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              EmojiTile(g.s('emoji')),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(child: Text(g.s('name'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(15.5, w: FontWeight.w500))),
                        Text('${g.i('pct')}%', style: Pk.num(15, c: g.s('status') == 'behind' ? Pk.amber : Pk.lime)),
                      ],
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${g.money('saved')}  ${l.ofLimit(g.money('target'))}${g.sn('deadline_label') != null ? '  ·  ${l.byDate(g.s('deadline_label'))}' : ''}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Pk.num(12.5, c: Pk.muted, w: FontWeight.w400),
                    ),
                    const SizedBox(height: 8),
                    SegBar(pct: g.i('pct'), color: g.s('status') == 'behind' ? Pk.amber : Pk.lime, height: 8),
                    if (g.s('status') == 'behind' && g.paise('monthly_need') > 0) ...[
                      const SizedBox(height: 6),
                      Text(l.needPerMonth(g.money('monthly_need')), style: Pk.text(12.5, c: Pk.amber)),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

// ---------- 4. Spend by category ----------
class SpendByCategory extends StatelessWidget {
  const SpendByCategory({super.key, required this.data, this.topN = 5});
  final Json data;
  final int topN;

  @override
  Widget build(BuildContext context) {
    final rows = data.l('this_month');
    if (rows.isEmpty) return _Quiet(L.of(context).noTransactions);
    final top = rows.take(topN).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(data.money('total'), style: Pk.num(26, c: Pk.bone, ls: -0.5)),
        const SizedBox(height: 12),
        SizedBox(height: 14, width: double.infinity, child: CustomPaint(painter: _StackBar([for (final r in top) r.i('pct')]))),
        const SizedBox(height: 14),
        for (final (i, r) in top.indexed)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 5),
            child: Row(
              children: [
                Container(width: 9, height: 9, color: Pk.series[i % Pk.series.length]),
                const SizedBox(width: 10),
                Expanded(child: Text(r.s('name'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(14.5))),
                Text('${r.i('pct')}%', style: Pk.num(12, c: Pk.faint, w: FontWeight.w400)),
                const SizedBox(width: 12),
                SizedBox(width: 84, child: Text(r.money('amount'), textAlign: TextAlign.right, style: Pk.num(14))),
              ],
            ),
          ),
      ],
    );
  }
}

class _StackBar extends CustomPainter {
  _StackBar(this.pcts);
  final List<int> pcts;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = Pk.line);
    double x = 0;
    for (final (i, p) in pcts.indexed) {
      final w = size.width * p / 100;
      if (w <= 0) continue;
      canvas.drawRect(Rect.fromLTWH(x, 0, math.max(0, w - 2), size.height), Paint()..color = Pk.series[i % Pk.series.length]);
      x += w;
    }
  }

  @override
  bool shouldRepaint(_StackBar old) => old.pcts != pcts;
}

// ---------- 5. Cash flow ----------
class CashFlowChart extends StatelessWidget {
  const CashFlowChart({super.key, required this.data, this.weeks = false});
  final Json data;
  final bool weeks;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final all = weeks ? data.l('weeks') : data.l('months');
    final rows = all.length > 6 ? all.sublist(all.length - 6) : all;
    if (rows.isEmpty) return _Quiet(l.noTransactions);
    final last = rows.last;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            _Legend(Pk.bone, l.income, last.money('income')),
            const SizedBox(width: 20),
            _Legend(Pk.lime, l.spend, last.money('spend')),
          ],
        ),
        const SizedBox(height: 14),
        SizedBox(
          height: 96,
          width: double.infinity,
          child: CustomPaint(painter: _PairBars([for (final r in rows) (r.paise('income'), r.paise('spend'))])),
        ),
        const SizedBox(height: 6),
        Row(children: [for (final r in rows) Expanded(child: Text(r.s('label').toUpperCase(), textAlign: TextAlign.center, maxLines: 1, style: Pk.label(c: Pk.faint, size: 9.5)))]),
      ],
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend(this.color, this.label, this.value);
  final Color color;
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 9, height: 9, color: color),
        const SizedBox(width: 8),
        Text('${label.toUpperCase()}  ', style: Pk.label(c: Pk.faint, size: 10)),
        Text(value, style: Pk.num(13.5)),
      ],
    );
  }
}

class _PairBars extends CustomPainter {
  _PairBars(this.pairs);
  final List<(int, int)> pairs;

  @override
  void paint(Canvas canvas, Size size) {
    // Bar heights are a drawing scale only; every figure shown as text comes from the API.
    final peak = pairs.fold<int>(1, (m, p) => math.max(m, math.max(p.$1, p.$2)));
    final slot = size.width / pairs.length;
    final barW = math.min(14.0, slot * 0.28);
    canvas.drawLine(Offset(0, size.height - 0.5), Offset(size.width, size.height - 0.5), Paint()..color = Pk.line);
    for (final (i, p) in pairs.indexed) {
      final cx = slot * i + slot / 2;
      final hi = size.height * p.$1 / peak, hs = size.height * p.$2 / peak;
      final last = i == pairs.length - 1;
      canvas.drawRect(Rect.fromLTWH(cx - barW - 1.5, size.height - hi, barW, hi), Paint()..color = last ? Pk.bone : Pk.bone.withValues(alpha: 0.38));
      canvas.drawRect(Rect.fromLTWH(cx + 1.5, size.height - hs, barW, hs), Paint()..color = last ? Pk.lime : Pk.lime.withValues(alpha: 0.38));
    }
  }

  @override
  bool shouldRepaint(_PairBars old) => old.pairs != pairs;
}

// ---------- 6. Transactions ----------
class TxnRows extends StatelessWidget {
  const TxnRows({super.key, required this.items, this.onTap});
  final List<Json> items;
  final void Function(Json txn)? onTap;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return _Quiet(L.of(context).noTransactions);
    return Column(
      children: [
        for (final (i, t) in items.indexed) ...[
          if (i > 0) const Stitch(vertical: 2),
          Pressable(onTap: onTap == null ? null : () => onTap!(t), scale: 0.99, child: TxnRow(t: t)),
        ],
      ],
    );
  }
}

class TxnRow extends StatelessWidget {
  const TxnRow({super.key, required this.t});
  final Json t;

  @override
  Widget build(BuildContext context) {
    final credit = t.s('direction') == 'credit';
    final excluded = t.s('spend_class') == 'excluded';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          EmojiTile(t.s('emoji'), size: 34),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(t.s('merchant'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(15, w: FontWeight.w500, c: excluded ? Pk.faint : Pk.bone)),
                const SizedBox(height: 2),
                Text('${t.s('date_label')} · ${t.s('category')}${t.b('is_split') ? ' · ÷' : ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(12.5, c: Pk.faint)),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Text(
            '${credit ? '+' : ''}${t.money('amount')}',
            style: Pk.num(14.5, c: excluded ? Pk.faint : credit ? Pk.lime : Pk.bone).copyWith(decoration: excluded ? TextDecoration.lineThrough : null),
          ),
        ],
      ),
    );
  }
}

// ---------- 7. Bills & EMIs ----------
String dueLabel(L l, int days) => days < 0 ? l.overdue : days == 0 ? l.dueToday : days == 1 ? l.dueTomorrow : l.dueIn(days);

class BillRows extends StatelessWidget {
  const BillRows({super.key, required this.items});
  final List<Json> items;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    if (items.isEmpty) return _Quiet(l.noBills);
    return Column(
      children: [
        for (final (i, b) in items.indexed) ...[
          if (i > 0) const Stitch(vertical: 2),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(
              children: [
                SizedBox(
                  width: 48,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(b.s('due_label').split(' ').first, style: Pk.num(18, c: b.i('days_until') <= 2 ? Pk.amber : Pk.bone, h: 1)),
                      Text(b.s('due_label').split(' ').skip(1).join(' ').toUpperCase(), style: Pk.label(c: Pk.faint, size: 9.5)),
                    ],
                  ),
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(b.s('name'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(15, w: FontWeight.w500)),
                      const SizedBox(height: 2),
                      Text('${dueLabel(l, b.i('days_until'))}${b.b('autopay') ? ' · ${l.autopay}' : ''}', style: Pk.text(12.5, c: b.i('days_until') <= 2 ? Pk.amber : Pk.faint)),
                    ],
                  ),
                ),
                Text('${b.b('variable') ? '~' : ''}${b.money('amount')}', style: Pk.num(14.5)),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

// ---------- 8. Net worth ----------
class NetWorthBlock extends StatelessWidget {
  const NetWorthBlock({super.key, required this.data});
  final Json data;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final rows = data.l('breakdown');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text(data.money('total'), style: Pk.num(30, c: data.paise('total') < 0 ? Pk.coral : Pk.bone, ls: -0.8))),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: _Side(l.assets, data.money('assets'), Pk.lime)),
            const SizedBox(width: 12),
            Expanded(child: _Side(l.liabilities, data.money('liabilities'), Pk.coral)),
          ],
        ),
        const Stitch(vertical: 12),
        for (final r in rows)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              children: [
                Container(width: 9, height: 9, color: r.s('side') == 'asset' ? Pk.lime : Pk.coral),
                const SizedBox(width: 10),
                Expanded(child: Text(r.s('label'), style: Pk.text(14.5))),
                Text(r.money('amount'), style: Pk.num(14)),
              ],
            ),
          ),
      ],
    );
  }
}

class _Side extends StatelessWidget {
  const _Side(this.label, this.value, this.color);
  final String label;
  final String value;
  final Color color;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(border: Border(left: BorderSide(color: color, width: 3)), color: Pk.raised),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label.toUpperCase(), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.label(c: Pk.faint, size: 9.5)),
          const SizedBox(height: 4),
          FittedBox(fit: BoxFit.scaleDown, child: Text(value, style: Pk.num(15))),
        ],
      ),
    );
  }
}

// ---------- 9. Investments (view only: no buy, invest or SIP buttons anywhere) ----------
class InvestmentsBlock extends StatelessWidget {
  const InvestmentsBlock({super.key, required this.data, this.maxItems = 3, this.showNote = true});
  final Json data;
  final int maxItems;
  final bool showNote;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final holdings = data.l('holdings');
    if (holdings.isEmpty) return _Quiet(l.noInvestments);
    final up = data.s('week_direction') != 'down';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(child: FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text(data.money('total'), style: Pk.num(28, ls: -0.6)))),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(l.weekChange.toUpperCase(), style: Pk.label(c: Pk.faint, size: 9.5)),
                Text('${up ? '▲' : '▼'} ${data.money('week_change_abs')}', style: Pk.num(14, c: up ? Pk.lime : Pk.coral)),
              ],
            ),
          ],
        ),
        const Stitch(vertical: 12),
        for (final h in holdings.take(maxItems))
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 5),
            child: Row(
              children: [
                Expanded(child: Text(h.s('name'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(14.5))),
                const SizedBox(width: 10),
                Text(h.b('approx') && h.paise('value') == 0 ? h.s('detail') : h.money('value'), style: Pk.num(14)),
              ],
            ),
          ),
        if (showNote) ...[const SizedBox(height: 8), Text(l.viewOnly, style: Pk.text(12, c: Pk.faint, h: 1.35))],
      ],
    );
  }
}

// ---------- 10. Insight ----------
class InsightBody extends ConsumerWidget {
  const InsightBody({super.key, required this.insight, this.showProposal = true});
  final Json insight;
  final bool showProposal;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final proposal = insight['proposal'] is Map ? insight.m('proposal') : null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(insight.s('title'), style: Pk.text(18, w: FontWeight.w600, h: 1.25)),
        const SizedBox(height: 6),
        Text(insight.s('body'), style: Pk.text(14.5, c: Pk.muted, h: 1.45)),
        if (showProposal && proposal != null) ...[const SizedBox(height: 14), ProposalCard(proposal: proposal, inset: true)],
      ],
    );
  }
}

/// The confirm card. A change the mascot suggests runs only when Confirm is tapped here.
class ProposalCard extends ConsumerStatefulWidget {
  const ProposalCard({super.key, required this.proposal, this.inset = false, this.onDone});
  final Json proposal;
  final bool inset;
  final void Function(bool accepted)? onDone;

  @override
  ConsumerState<ProposalCard> createState() => _ProposalCardState();
}

class _ProposalCardState extends ConsumerState<ProposalCard> {
  bool _busy = false;

  Future<void> _decide(bool accept) async {
    if (_busy) return;
    setState(() => _busy = true);
    final l = L.of(context);
    final id = widget.proposal.s('id');
    final notifier = ref.read(appProvider.notifier);
    var ok = true;
    if (accept) {
      ok = await notifier.acceptProposal(id);
    } else {
      await notifier.declineProposal(id);
    }
    if (!mounted) return;
    setState(() => _busy = false);
    if (accept) toast(context, ok ? l.proposalDone : l.proposalFailed);
    widget.onDone?.call(accept && ok);
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final p = widget.proposal;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: widget.inset ? Pk.raised : Pk.surface,
        borderRadius: BorderRadius.circular(widget.inset ? Pk.rSm : Pk.r),
        border: Border.all(color: Pk.lime.withValues(alpha: 0.6)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (p.s('from_emoji').isNotEmpty) ...[EmojiTile(p.s('from_emoji'), size: 30), const Padding(padding: EdgeInsets.symmetric(horizontal: 6), child: Icon(Icons.arrow_forward, size: 14, color: Pk.lime))],
              if (p.s('to_emoji').isNotEmpty) EmojiTile(p.s('to_emoji'), size: 30),
              const Spacer(),
              Text(p.money('amount'), style: Pk.num(18, c: Pk.lime)),
            ],
          ),
          const SizedBox(height: 10),
          Text(p.s('title'), style: Pk.text(16, w: FontWeight.w600, h: 1.3)),
          if (p.s('body').isNotEmpty) ...[const SizedBox(height: 4), Text(p.s('body'), style: Pk.text(13.5, c: Pk.muted, h: 1.4))],
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: BlockButton(label: l.confirm, icon: Icons.check, busy: _busy, onTap: () => _decide(true))),
              const SizedBox(width: 10),
              GhostButton(label: l.notNow, onTap: _busy ? null : () => _decide(false)),
            ],
          ),
          const SizedBox(height: 8),
          Text(l.confirmCardNote, style: Pk.text(11.5, c: Pk.faint)),
        ],
      ),
    );
  }
}

// ---------- 11. Pulse ----------
class PulseBody extends StatelessWidget {
  const PulseBody({super.key, required this.item});
  final Json item;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final lines = item.strings('for_you');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(item.s('title'), style: Pk.text(17, w: FontWeight.w600, h: 1.25)),
        const SizedBox(height: 6),
        Text(item.s('summary'), style: Pk.text(14, c: Pk.muted, h: 1.45)),
        if (lines.isNotEmpty) ...[
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: const BoxDecoration(color: Pk.raised, border: Border(left: BorderSide(color: Pk.lime, width: 3))),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l.forYou.toUpperCase(), style: Pk.label(c: Pk.lime, size: 10)),
                const SizedBox(height: 6),
                for (final line in lines) Padding(padding: const EdgeInsets.only(top: 2), child: Text(line, style: Pk.text(14.5, h: 1.4))),
              ],
            ),
          ),
        ],
        const SizedBox(height: 4),
        Pressable(
          onTap: () => launchUrl(Uri.parse(item.s('source_url')), mode: LaunchMode.externalApplication),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.link, size: 14, color: Pk.faint),
              const SizedBox(width: 6),
              Flexible(child: Text(item.s('source_name'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(12.5, c: Pk.muted).copyWith(decoration: TextDecoration.underline, decorationColor: Pk.faint))),
            ],
          ),
        ),
      ],
    );
  }
}

// ---------- 12. Group pot ----------
class GroupPotBlock extends StatelessWidget {
  const GroupPotBlock({super.key, required this.group});
  final Json group;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final pot = group['pot'] is Map ? group.m('pot') : null;
    final position = group.s('my_position');
    final members = group.l('members');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(group.s('emoji'), style: const TextStyle(fontSize: 22)),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                position == 'owes' ? l.youOwe(group.m('my_balance_abs').s('display')) : position == 'owed' ? l.youAreOwed(group.m('my_balance_abs').s('display')) : l.allSettled,
                style: Pk.text(15.5, w: FontWeight.w500, c: Pk.statusColor(position)),
              ),
            ),
          ],
        ),
        if (pot != null) ...[
          const SizedBox(height: 12),
          Row(
            children: [
              Text(l.pot.toUpperCase(), style: Pk.label(c: Pk.faint, size: 10)),
              const SizedBox(width: 8),
              Expanded(child: Text('${pot.money('saved')}  ${l.ofLimit(pot.money('target'))}', style: Pk.num(13.5))),
              Text('${pot.i('pct')}%', style: Pk.num(13.5, c: Pk.lime)),
            ],
          ),
          const SizedBox(height: 8),
          SegBar(pct: pot.i('pct'), height: 8),
        ],
        const SizedBox(height: 12),
        Row(
          children: [
            for (final m in members.take(6)) Padding(padding: const EdgeInsets.only(right: 6), child: InitialTile(m.s('name'), highlight: m.b('is_me'))),
            const Spacer(),
            Text(l.membersCount(group.i('member_count')), style: Pk.text(12.5, c: Pk.faint)),
          ],
        ),
      ],
    );
  }
}
