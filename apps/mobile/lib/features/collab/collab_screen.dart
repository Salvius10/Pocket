import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/state.dart';
import '../../core/theme.dart';
import '../../core/ui.dart';
import '../../l10n/app_localizations.dart';
import '../home/widgets.dart';
import '../shell/shell.dart';

String groupTypeLabel(L l, String type) => switch (type) { 'family' => l.typeFamily, 'trip' => l.typeTrip, 'flatmates' => l.typeFlatmates, _ => l.typeCustom };

/// Collab tab: money with other people. Pocket tracks who owes whom; it never holds money.
class CollabScreen extends ConsumerWidget {
  const CollabScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final groups = ref.watch(appProvider.select((s) => s.groups));
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 120),
        children: [
          ScreenTitle(l.collabTitle),
          if (groups.isEmpty) StateNote(icon: Icons.group_outlined, title: l.noGroups, body: l.noGroupsBody),
          for (final (i, g) in groups.indexed)
            Padding(
              padding: const EdgeInsets.fromLTRB(Pk.pad, 0, Pk.pad, Pk.gap),
              child: Rise(
                index: i,
                child: PCard(
                  onTap: () => context.push('/group/${g.s('id')}'),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(children: [Expanded(child: Text(g.s('name'), style: Pk.text(19, w: FontWeight.w600))), Tag(groupTypeLabel(l, g.s('type')))]),
                      const SizedBox(height: 12),
                      GroupPotBlock(group: g),
                    ],
                  ),
                ),
              ),
            ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: Pk.pad),
            child: Row(
              children: [
                Expanded(child: GhostButton(label: l.newGroup, icon: Icons.add, dense: true, onTap: () => showPocketSheet<void>(context, title: l.newGroup, builder: (_) => const _NewGroupForm()))),
                const SizedBox(width: 10),
                Expanded(child: GhostButton(label: l.joinGroup, icon: Icons.tag, dense: true, onTap: () => showPocketSheet<void>(context, title: l.joinGroup, builder: (_) => const _JoinForm()))),
              ],
            ),
          ),
          Padding(padding: const EdgeInsets.fromLTRB(Pk.pad, 16, Pk.pad, 0), child: Text(l.pocketNeverHolds, style: Pk.text(12.5, c: Pk.faint, h: 1.4))),
        ],
      ),
    );
  }
}

class _NewGroupForm extends ConsumerStatefulWidget {
  const _NewGroupForm();
  @override
  ConsumerState<_NewGroupForm> createState() => _NewGroupFormState();
}

class _NewGroupFormState extends ConsumerState<_NewGroupForm> {
  final _name = TextEditingController();
  String _type = 'trip';
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(controller: _name, autofocus: true, onChanged: (_) => setState(() {}), style: Pk.text(16), decoration: InputDecoration(labelText: l.groupName)),
        const SizedBox(height: 12),
        Wrap(spacing: 8, children: [for (final t in const ['trip', 'flatmates', 'family', 'custom']) PChip(label: groupTypeLabel(l, t), selected: _type == t, onTap: () => setState(() => _type = t))]),
        const SizedBox(height: 18),
        BlockButton(
          label: l.save,
          busy: _busy,
          onTap: _name.text.trim().isEmpty
              ? null
              : () async {
                  setState(() => _busy = true);
                  final n = ref.read(appProvider.notifier);
                  await n.send('POST', '/v1/groups', {'name': _name.text.trim(), 'type': _type, 'emoji': const {'trip': '🧳', 'flatmates': '🏠', 'family': '👪', 'custom': '🤝'}[_type]});
                  await n.sync();
                  if (context.mounted) Navigator.of(context).pop();
                },
        ),
      ],
    );
  }
}

class _JoinForm extends ConsumerStatefulWidget {
  const _JoinForm();
  @override
  ConsumerState<_JoinForm> createState() => _JoinFormState();
}

class _JoinFormState extends ConsumerState<_JoinForm> {
  final _code = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: _code,
          autofocus: true,
          textCapitalization: TextCapitalization.characters,
          maxLength: 6,
          onChanged: (_) => setState(() {}),
          style: Pk.num(26, ls: 6),
          decoration: InputDecoration(labelText: l.inviteCode, counterText: ''),
        ),
        const SizedBox(height: 18),
        BlockButton(
          label: l.joinGroup,
          busy: _busy,
          onTap: _code.text.trim().length != 6
              ? null
              : () async {
                  setState(() => _busy = true);
                  final n = ref.read(appProvider.notifier);
                  final ok = await n.send('POST', '/v1/groups/join', {'code': _code.text.trim().toUpperCase()});
                  await n.sync();
                  if (!context.mounted) return;
                  if (ok) {
                    Navigator.of(context).pop();
                  } else {
                    setState(() => _busy = false);
                    toast(context, l.errorTitle);
                  }
                },
        ),
      ],
    );
  }
}

/// One group: balances, settle-up by UPI, expenses, pot, privacy.
class GroupScreen extends ConsumerWidget {
  const GroupScreen({super.key, required this.groupId});
  final String groupId;

  String get _path => '/v1/groups/$groupId';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final result = ref.watch(fetchProvider(_path));
    return Scaffold(
      body: SafeArea(
        child: result.when(
          loading: () => ListView(padding: const EdgeInsets.all(Pk.pad), children: const [SizedBox(height: 50), Skeleton(height: 140), SizedBox(height: 12), Skeleton(height: 220)]),
          error: (_, _) => Center(child: StateNote(icon: Icons.cloud_off_outlined, title: l.errorTitle, body: l.errorBody, action: l.retry, onAction: () => ref.invalidate(fetchProvider(_path)))),
          data: (g) => _body(context, ref, g),
        ),
      ),
    );
  }

  Future<void> _refresh(WidgetRef ref) async {
    ref.invalidate(fetchProvider(_path));
    await ref.read(appProvider.notifier).sync();
  }

  Widget _body(BuildContext context, WidgetRef ref, Json g) {
    final l = L.of(context);
    final members = g.l('members');
    final plan = g.l('settle_plan');
    final expenses = g.l('expenses');
    final pending = g.l('settlements').where((s) => s.s('status') != 'confirmed').toList();
    final pot = g['pot'] is Map ? g.m('pot') : null;
    final budget = g['budget'] is Map ? g.m('budget') : null;
    return ListView(
      padding: const EdgeInsets.fromLTRB(Pk.pad, 8, Pk.pad, 40),
      children: [
        Row(
          children: [
            IconButton(onPressed: () => context.pop(), icon: const Icon(Icons.arrow_back, color: Pk.bone), tooltip: MaterialLocalizations.of(context).backButtonTooltip),
            const Spacer(),
            if (g.sn('invite_code') != null)
              Pressable(
                onTap: () {
                  Clipboard.setData(ClipboardData(text: g.s('invite_code')));
                  toast(context, l.copied);
                },
                semantics: l.inviteCode,
                child: Row(mainAxisSize: MainAxisSize.min, children: [Text('${l.inviteCode.toUpperCase()}  ', style: Pk.label(c: Pk.faint, size: 10)), Text(g.s('invite_code'), style: Pk.num(15, c: Pk.lime, ls: 2)), const SizedBox(width: 6), const Icon(Icons.copy, size: 13, color: Pk.faint)]),
              ),
          ],
        ),
        const SizedBox(height: 4),
        Row(children: [Text(g.s('emoji'), style: const TextStyle(fontSize: 30)), const SizedBox(width: 12), Expanded(child: Text(g.s('name'), style: Pk.text(28, w: FontWeight.w600, h: 1.1, ls: -0.5)))]),
        const SizedBox(height: 16),
        if (pot != null || budget != null)
          PCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (pot != null) ...[
                  SectionLabel(l.pot, trailing: pot.sn('deadline_label') == null ? null : Text(l.byDate(pot.s('deadline_label')).toUpperCase(), style: Pk.label(c: Pk.faint, size: 10))),
                  const SizedBox(height: 10),
                  Row(crossAxisAlignment: CrossAxisAlignment.end, children: [Expanded(child: Text(pot.money('saved'), style: Pk.num(28, c: Pk.lime, ls: -0.6))), Text(l.ofLimit(pot.money('target')), style: Pk.num(13, c: Pk.muted, w: FontWeight.w400))]),
                  const SizedBox(height: 10),
                  SegBar(pct: pot.i('pct'), height: 10),
                  const SizedBox(height: 12),
                  GhostButton(label: l.addToPot, icon: Icons.add, dense: true, onTap: () => _amountSheet(context, ref, l.addToPot, (paise, _) => ref.read(appProvider.notifier).send('POST', '$_path/pot', {'amount_paise': paise}))),
                ],
                if (pot != null && budget != null) const Stitch(vertical: 14),
                if (budget != null) ...[
                  SectionLabel(l.sharedBudget, trailing: Text(l.thisMonth.toUpperCase(), style: Pk.label(c: Pk.faint, size: 10))),
                  const SizedBox(height: 10),
                  Row(crossAxisAlignment: CrossAxisAlignment.end, children: [Expanded(child: Text(budget.money('spent'), style: Pk.num(24, ls: -0.5))), Text(l.ofLimit(budget.money('limit')), style: Pk.num(13, c: Pk.muted, w: FontWeight.w400))]),
                  const SizedBox(height: 10),
                  SegBar(pct: budget.i('pct'), color: budget.i('pct') > 100 ? Pk.coral : Pk.lime, height: 10),
                ],
              ],
            ),
          ),
        const SizedBox(height: Pk.gap),
        PCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionLabel(l.members, trailing: _link(l.addGuest, () => _guestSheet(context, ref))),
              const SizedBox(height: 10),
              for (final m in members)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      InitialTile(m.s('name'), highlight: m.b('is_me'), size: 34),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(m.b('is_me') ? '${m.s('name')} (${l.you})' : m.s('name'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(15, w: FontWeight.w500)),
                            if (m.b('is_guest')) Text(l.guest, style: Pk.text(12, c: Pk.faint)),
                          ],
                        ),
                      ),
                      Text(
                        m.s('position') == 'even' ? '—' : '${m.s('position') == 'owed' ? '+' : '-'}${m.m('balance_abs').s('display')}',
                        style: Pk.num(14.5, c: Pk.statusColor(m.s('position'))),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
        if (plan.isNotEmpty || pending.isNotEmpty) ...[
          const SizedBox(height: Pk.gap),
          PCard(
            border: Pk.lime.withValues(alpha: 0.5),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SectionLabel(l.settleUp, color: Pk.lime),
                const SizedBox(height: 6),
                for (final p in plan)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Row(
                      children: [
                        Expanded(child: Text(l.pays(p.s('from_name').split(' ').first, p.s('to_name').split(' ').first), style: Pk.text(15))),
                        Text(p.money('amount'), style: Pk.num(15)),
                        const SizedBox(width: 10),
                        GhostButton(label: p.b('i_pay') ? l.payByUpi : l.settleUp, dense: true, color: p.b('i_pay') ? Pk.lime : Pk.bone, onTap: () => _startSettle(context, ref, g, p)),
                      ],
                    ),
                  ),
                if (pending.isNotEmpty) const Stitch(vertical: 8),
                for (final s in pending)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Row(
                      children: [
                        Expanded(child: Text('${s.s('from_name').split(' ').first} → ${s.s('to_name').split(' ').first} · ${s.money('amount')}', style: Pk.num(13, c: Pk.muted, w: FontWeight.w400))),
                        Tag(_statusLabel(l, s.s('status')), color: s.s('status') == 'marked_paid' ? Pk.amber : Pk.muted),
                        const SizedBox(width: 8),
                        if (s.s('status') == 'marked_paid')
                          GhostButton(label: l.confirmReceived, dense: true, onTap: () async {
                            await ref.read(appProvider.notifier).send('POST', '$_path/settlements/${s.s('id')}/status', {'status': 'confirmed'});
                            await _refresh(ref);
                          })
                        else
                          GhostButton(label: l.payByUpi, dense: true, onTap: () => _upiSheet(context, ref, g, s.s('id'), s.sn('upi_link'), s.money('amount'), s.s('to_name'), s.s('status'))),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],
        const SizedBox(height: Pk.gap),
        PCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionLabel('${l.expenses} · ${g.i('expense_count')}', trailing: _link(l.addExpense, () => _expenseSheet(context, ref, g))),
              const SizedBox(height: 6),
              for (final (i, e) in expenses.take(25).indexed) ...[
                if (i > 0) const Stitch(vertical: 2),
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(e.s('description'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(15, w: FontWeight.w500)),
                            const SizedBox(height: 2),
                            Text('${e.s('date_label')} · ${l.paidBy} ${e.b('paid_by_me') ? l.you : e.s('paid_by').split(' ').first} · ${l.yourShare(e.money('my_share'))}', maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(12.5, c: Pk.faint)),
                          ],
                        ),
                      ),
                      const SizedBox(width: 10),
                      Text(e.money('amount'), style: Pk.num(14.5)),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: Pk.gap),
        PCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionLabel(l.privacyGroup),
              const SizedBox(height: 10),
              Text(l.privacyGroupNote, style: Pk.text(14, c: Pk.muted, h: 1.4)),
              const SizedBox(height: 10),
              Row(children: [const Icon(Icons.lock_outline, size: 16, color: Pk.lime), const SizedBox(width: 8), Text(l.shareNothing, style: Pk.text(14.5, w: FontWeight.w500))]),
            ],
          ),
        ),
        const SizedBox(height: 16),
        Text(l.pocketNeverHolds, style: Pk.text(12.5, c: Pk.faint, h: 1.4)),
      ],
    );
  }

  String _statusLabel(L l, String s) => switch (s) { 'link_opened' => l.statusLinkOpened, 'marked_paid' => l.statusMarkedPaid, 'confirmed' => l.statusConfirmed, _ => l.statusPending };

  Widget _link(String label, VoidCallback onTap) => Pressable(
        onTap: onTap,
        semantics: label,
        child: Row(mainAxisSize: MainAxisSize.min, children: [const Icon(Icons.add, size: 14, color: Pk.lime), const SizedBox(width: 4), Text(label.toUpperCase(), style: Pk.label(c: Pk.lime, size: 10.5))]),
      );

  Future<void> _startSettle(BuildContext context, WidgetRef ref, Json g, Json p) async {
    final api = ref.read(apiProvider);
    try {
      final out = await api.post('$_path/settlements', {'from_member_id': p.s('from_id'), 'to_member_id': p.s('to_id'), 'amount_paise': p.paise('amount')});
      ref.invalidate(fetchProvider(_path));
      if (context.mounted) _upiSheet(context, ref, g, out.s('settlement_id'), out.sn('upi_link'), p.money('amount'), p.s('to_name'), 'pending');
    } catch (_) {
      if (context.mounted) toast(context, L.of(context).errorTitle);
    }
  }

  /// Settle-up: a upi://pay link, a QR of the same link, and the UPI ID to copy. The payment
  /// itself happens in the user's own UPI app.
  void _upiSheet(BuildContext context, WidgetRef ref, Json g, String settlementId, String? upiLink, String amount, String toName, String status) {
    final l = L.of(context);
    final vpa = upiLink == null ? null : Uri.tryParse(upiLink)?.queryParameters['pa'];
    Future<void> setStatus(String s) async {
      await ref.read(appProvider.notifier).send('POST', '$_path/settlements/$settlementId/status', {'status': s});
      await _refresh(ref);
    }

    showPocketSheet<void>(
      context,
      title: '$amount → ${toName.split(' ').first}',
      tall: true,
      builder: (ctx) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (upiLink != null) ...[
            Center(
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: Pk.bone, borderRadius: BorderRadius.circular(Pk.r)),
                child: QrImageView(data: upiLink, size: 190, backgroundColor: Pk.bone, padding: EdgeInsets.zero),
              ),
            ),
            const SizedBox(height: 16),
            BlockButton(
              label: l.openUpiApp,
              icon: Icons.open_in_new,
              onTap: () async {
                final opened = await launchUrl(Uri.parse(upiLink), mode: LaunchMode.externalApplication).catchError((_) => false);
                if (opened && status == 'pending') await setStatus('link_opened');
              },
            ),
            const SizedBox(height: 10),
            GhostButton(
              label: '${l.copyUpiId} · ${vpa ?? ''}',
              icon: Icons.copy,
              onTap: () {
                Clipboard.setData(ClipboardData(text: vpa ?? ''));
                toast(ctx, l.copied);
              },
            ),
            const SizedBox(height: 10),
          ],
          GhostButton(
            label: l.markPaid,
            icon: Icons.check,
            color: Pk.lime,
            onTap: () async {
              Navigator.of(ctx).pop();
              await setStatus('marked_paid');
            },
          ),
          const SizedBox(height: 14),
          Text(l.pocketNeverHolds, style: Pk.text(12.5, c: Pk.muted, h: 1.4)),
          if ((vpa ?? '').endsWith('@pocketdemo')) Padding(padding: const EdgeInsets.only(top: 6), child: Text(l.demoUpiNote, style: Pk.text(12.5, c: Pk.amber, h: 1.4))),
        ],
      ),
    );
  }

  void _amountSheet(BuildContext context, WidgetRef ref, String title, Future<bool> Function(int paise, String note) submit) {
    showPocketSheet<void>(
      context,
      title: title,
      builder: (ctx) => _AmountForm(
        withNote: false,
        onSubmit: (paise, note) async {
          await submit(paise, note);
          await _refresh(ref);
        },
      ),
    );
  }

  void _expenseSheet(BuildContext context, WidgetRef ref, Json g) {
    final l = L.of(context);
    showPocketSheet<void>(
      context,
      title: l.addExpense,
      builder: (ctx) => _AmountForm(
        withNote: true,
        footnote: '${l.splitEqual} · ${l.membersCount(g.l('members').length)}',
        onSubmit: (paise, note) async {
          await ref.read(appProvider.notifier).send('POST', '$_path/expenses', {'amount_paise': paise, 'description': note, 'split_method': 'equal'});
          await _refresh(ref);
        },
      ),
    );
  }

  void _guestSheet(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final name = TextEditingController();
    final vpa = TextEditingController();
    showPocketSheet<void>(
      context,
      title: l.addGuest,
      builder: (ctx) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(controller: name, autofocus: true, style: Pk.text(16), decoration: InputDecoration(labelText: l.nameLabel)),
          const SizedBox(height: 12),
          TextField(controller: vpa, style: Pk.num(15), decoration: InputDecoration(labelText: l.guestUpi)),
          const SizedBox(height: 18),
          BlockButton(
            label: l.add,
            onTap: () async {
              if (name.text.trim().isEmpty) return;
              Navigator.of(ctx).pop();
              await ref.read(appProvider.notifier).send('POST', '$_path/guests', {'name': name.text.trim(), if (vpa.text.trim().isNotEmpty) 'vpa': vpa.text.trim()});
              await _refresh(ref);
            },
          ),
        ],
      ),
    );
  }
}

class _AmountForm extends StatefulWidget {
  const _AmountForm({required this.onSubmit, required this.withNote, this.footnote});
  final Future<void> Function(int paise, String note) onSubmit;
  final bool withNote;
  final String? footnote;

  @override
  State<_AmountForm> createState() => _AmountFormState();
}

class _AmountFormState extends State<_AmountForm> {
  final _amount = TextEditingController();
  final _note = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _amount.dispose();
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final paise = rupeesToPaise(_amount.text);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: _amount,
          autofocus: true,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
          onChanged: (_) => setState(() {}),
          style: Pk.num(22),
          decoration: InputDecoration(labelText: l.amountRupees),
        ),
        if (widget.withNote) ...[const SizedBox(height: 12), TextField(controller: _note, style: Pk.text(15.5), decoration: InputDecoration(labelText: l.whatWasIt))],
        if (widget.footnote != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(widget.footnote!, style: Pk.text(13, c: Pk.muted))),
        const SizedBox(height: 18),
        BlockButton(
          label: paise == null ? l.add : '${l.add} ${displayPaise(paise)}',
          busy: _busy,
          onTap: paise == null || paise <= 0
              ? null
              : () async {
                  setState(() => _busy = true);
                  await widget.onSubmit(paise, _note.text.trim());
                  if (context.mounted) Navigator.of(context).pop();
                },
        ),
      ],
    );
  }
}
