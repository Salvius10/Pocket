import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/state.dart';
import '../../core/theme.dart';
import '../../core/ui.dart';
import '../../l10n/app_localizations.dart';
import '../home/widgets.dart';
import '../shell/shell.dart';

/// Plan tab: pockets (budgets), goals (savings) and the moves Poko suggests.
class PlanScreen extends ConsumerWidget {
  const PlanScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final app = ref.watch(appProvider);
    final s = app.summary;
    final proposals = app.proposals;
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 120),
        children: [
          ScreenTitle(l.planTitle),
          if (proposals.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(Pk.pad, 0, Pk.pad, Pk.gap),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SectionLabel(l.suggested, color: Pk.lime),
                  const SizedBox(height: 10),
                  for (final p in proposals.take(3)) Padding(padding: const EdgeInsets.only(bottom: 10), child: ProposalCard(proposal: p)),
                ],
              ),
            ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: Pk.pad),
            child: PCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SectionLabel(l.wPockets, trailing: _AddLink(l.newPocket, () => _newPocket(context, ref))),
                  const SizedBox(height: 14),
                  PocketRows(items: s.l('pockets'), onTapItem: (p) => _pocketSheet(context, ref, p)),
                ],
              ),
            ),
          ),
          const SizedBox(height: Pk.gap),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: Pk.pad),
            child: PCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SectionLabel(l.wGoals, trailing: _AddLink(l.newGoal, () => _newGoal(context))),
                  const SizedBox(height: 14),
                  GoalRows(items: s.l('goals')),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(Pk.pad, Pk.gap, Pk.pad, 0),
            child: PCard(
              onTap: () => context.push('/report'),
              child: Row(
                children: [
                  const Icon(Icons.insert_chart_outlined, size: 20, color: Pk.lime),
                  const SizedBox(width: 12),
                  Expanded(child: Text(l.reportTitle, style: Pk.text(15.5, w: FontWeight.w600))),
                  const Icon(Icons.arrow_outward, size: 16, color: Pk.muted),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _pocketSheet(BuildContext context, WidgetRef ref, Json p) {
    final l = L.of(context);
    final paused = p.s('status') == 'paused';
    showPocketSheet<void>(
      context,
      title: '${p.s('emoji')}  ${p.s('name')}',
      builder: (ctx) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(p.money('spent'), style: Pk.num(32, ls: -0.8)),
          const SizedBox(height: 4),
          Text(l.ofLimit(p.money('limit')), style: Pk.num(14, c: Pk.muted, w: FontWeight.w400)),
          const SizedBox(height: 14),
          SegBar(pct: p.i('pct'), color: p.s('status') == 'ok' ? Pk.lime : Pk.statusColor(p.s('status')), height: 12),
          const SizedBox(height: 20),
          GhostButton(
            label: paused ? l.resumePocket : l.pausePocket,
            icon: paused ? Icons.play_arrow_outlined : Icons.pause_outlined,
            onTap: () async {
              Navigator.of(ctx).pop();
              final n = ref.read(appProvider.notifier);
              await n.send('PATCH', '/v1/pockets/${p.s('id')}', {'status': paused ? 'active' : 'paused'});
              await n.sync();
            },
          ),
        ],
      ),
    );
  }

  void _newPocket(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    showPocketSheet<void>(context, title: l.newPocket, tall: true, builder: (_) => const _PlanForm(goal: false));
  }

  void _newGoal(BuildContext context) {
    final l = L.of(context);
    showPocketSheet<void>(context, title: l.newGoal, builder: (_) => const _PlanForm(goal: true));
  }
}

class _AddLink extends StatelessWidget {
  const _AddLink(this.label, this.onTap);
  final String label;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      semantics: label,
      child: Row(mainAxisSize: MainAxisSize.min, children: [const Icon(Icons.add, size: 14, color: Pk.lime), const SizedBox(width: 4), Text(label.toUpperCase(), style: Pk.label(c: Pk.lime, size: 10.5))]),
    );
  }
}

class _PlanForm extends ConsumerStatefulWidget {
  const _PlanForm({required this.goal});
  final bool goal;

  @override
  ConsumerState<_PlanForm> createState() => _PlanFormState();
}

class _PlanFormState extends ConsumerState<_PlanForm> {
  final _name = TextEditingController();
  final _amount = TextEditingController();
  final Set<String> _cats = {};
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    _amount.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final categories = ref.watch(appProvider.select((s) => s.categories)).where((c) => c.s('kind') == 'expense').toList();
    final paise = rupeesToPaise(_amount.text);
    final ok = _name.text.trim().isNotEmpty && paise != null && paise > 0 && (widget.goal || _cats.isNotEmpty);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(controller: _name, autofocus: true, onChanged: (_) => setState(() {}), style: Pk.text(16), decoration: InputDecoration(labelText: l.nameLabel)),
        const SizedBox(height: 12),
        TextField(
          controller: _amount,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          onChanged: (_) => setState(() {}),
          style: Pk.num(20),
          decoration: InputDecoration(labelText: widget.goal ? l.targetAmount : l.monthlyLimit),
        ),
        if (!widget.goal) ...[
          const SizedBox(height: 14),
          Text(l.category.toUpperCase(), style: Pk.label()),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: [
              for (final c in categories)
                PChip(
                  label: '${c.s('emoji')} ${c.s('name')}',
                  selected: _cats.contains(c.s('id')),
                  onTap: () => setState(() => _cats.contains(c.s('id')) ? _cats.remove(c.s('id')) : _cats.add(c.s('id'))),
                ),
            ],
          ),
        ],
        const SizedBox(height: 18),
        BlockButton(
          label: paise == null ? l.save : '${l.save} · ${displayPaise(paise)}',
          busy: _busy,
          onTap: !ok
              ? null
              : () async {
                  setState(() => _busy = true);
                  final n = ref.read(appProvider.notifier);
                  if (widget.goal) {
                    await n.send('POST', '/v1/goals', {'name': _name.text.trim(), 'target_paise': paise});
                  } else {
                    await n.send('POST', '/v1/pockets', {'name': _name.text.trim(), 'monthly_limit_paise': paise, 'category_ids': _cats.toList()});
                  }
                  await n.sync();
                  if (context.mounted) Navigator.of(context).pop();
                },
        ),
      ],
    );
  }
}
