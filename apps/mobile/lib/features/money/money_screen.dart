import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/state.dart';
import '../../core/theme.dart';
import '../../core/ui.dart';
import '../../l10n/app_localizations.dart';
import '../home/widgets.dart';
import '../shell/shell.dart';

/// Money tab: one ledger for spend and income, accounts, bills & EMIs, investments (view only).
class MoneyScreen extends ConsumerStatefulWidget {
  const MoneyScreen({super.key});

  @override
  ConsumerState<MoneyScreen> createState() => _MoneyScreenState();
}

class _MoneyScreenState extends ConsumerState<MoneyScreen> {
  int _segment = 0;
  String _query = '';
  String? _direction;
  final _search = TextEditingController();

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final labels = [l.segTransactions, l.segAccounts, l.segBills, l.segInvestments];
    return SafeArea(
      bottom: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ScreenTitle(
            l.moneyTitle,
            trailing: _segment == 0 ? GhostButton(label: l.addCash, icon: Icons.add, dense: true, onTap: () => _addCash(context)) : null,
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: Pk.pad),
            child: Row(children: [for (final (i, label) in labels.indexed) Padding(padding: const EdgeInsets.only(right: 8), child: PChip(label: label, selected: _segment == i, onTap: () => setState(() => _segment = i)))]),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: switch (_segment) {
              0 => _transactions(context, l),
              1 => _Accounts(),
              2 => _Bills(),
              _ => _Investments(),
            },
          ),
        ],
      ),
    );
  }

  Widget _transactions(BuildContext context, L l) {
    final query = <String, String>{'limit': '80', if (_query.isNotEmpty) 'q': _query, if (_direction != null) 'direction': _direction!};
    final path = Uri(path: '/v1/transactions', queryParameters: query).toString();
    final result = ref.watch(fetchProvider(path));
    final cached = ref.watch(appProvider.select((s) => s.transactions));
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(Pk.pad, 4, Pk.pad, 8),
          child: TextField(
            controller: _search,
            onSubmitted: (v) => setState(() => _query = v.trim()),
            textInputAction: TextInputAction.search,
            style: Pk.text(15),
            decoration: InputDecoration(
              hintText: l.searchHint,
              isDense: true,
              prefixIcon: const Icon(Icons.search, size: 18, color: Pk.faint),
              suffixIcon: _query.isEmpty
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.close, size: 16, color: Pk.faint),
                      onPressed: () => setState(() {
                        _search.clear();
                        _query = '';
                      }),
                    ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: Pk.pad),
          child: Row(
            children: [
              for (final (label, value) in [(l.filterAll, null), (l.filterOut, 'debit'), (l.filterIn, 'credit')])
                Padding(padding: const EdgeInsets.only(right: 8), child: PChip(label: label, selected: _direction == value, onTap: () => setState(() => _direction = value))),
            ],
          ),
        ),
        Expanded(
          child: result.when(
            loading: () => ListView(padding: const EdgeInsets.all(Pk.pad), children: const [Skeleton(height: 320)]),
            // Offline: fall back to the cached recent transactions instead of an error wall.
            error: (_, _) => cached.isEmpty
                ? Center(child: StateNote(icon: Icons.cloud_off_outlined, title: l.errorTitle, body: l.errorBody, action: l.retry, onAction: () => ref.invalidate(fetchProvider(path))))
                : _txnList(context, cached),
            data: (data) {
              final items = data.l('items');
              if (items.isEmpty) return Center(child: StateNote(icon: Icons.receipt_long_outlined, title: l.noTransactions));
              return _txnList(context, items);
            },
          ),
        ),
      ],
    );
  }

  Widget _txnList(BuildContext context, List<Json> items) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(Pk.pad, 10, Pk.pad, 120),
      children: [PCard(padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6), child: TxnRows(items: items, onTap: (t) => _txnSheet(context, t)))],
    );
  }

  void _txnSheet(BuildContext context, Json t) {
    final l = L.of(context);
    final app = ref.read(appProvider);
    showPocketSheet<void>(
      context,
      title: t.s('merchant'),
      tall: true,
      builder: (ctx) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${t.s('direction') == 'credit' ? '+' : ''}${t.m('amount').s('exact')}', style: Pk.num(30, c: t.s('direction') == 'credit' ? Pk.lime : Pk.bone, ls: -0.6)),
          const SizedBox(height: 6),
          Text('${t.s('date_label')} · ${t.s('account')} · ${t.s('mode').toUpperCase()}', style: Pk.text(13.5, c: Pk.muted)),
          if (t.b('is_split')) Padding(padding: const EdgeInsets.only(top: 6), child: Text(l.yourShare(t.money('personal_amount')), style: Pk.text(13.5, c: Pk.lime))),
          const SizedBox(height: 6),
          Text(t.s('narration'), style: Pk.num(11.5, c: Pk.faint, w: FontWeight.w400)),
          const Stitch(vertical: 16),
          Text(l.changeCategory.toUpperCase(), style: Pk.label()),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            children: [
              for (final c in app.categories.where((c) => c.s('kind') == (t.s('direction') == 'credit' ? 'income' : 'expense')))
                PChip(
                  label: '${c.s('emoji')} ${c.s('name')}',
                  selected: c.s('id') == t.s('category_id'),
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    await ref.read(appProvider.notifier).recategorise(t.s('id'), c.s('id'));
                  },
                ),
            ],
          ),
          if (t.s('direction') == 'debit' && !t.b('is_split') && app.groups.isNotEmpty) ...[
            const Stitch(vertical: 16),
            Text(l.splitWithGroup.toUpperCase(), style: Pk.label()),
            const SizedBox(height: 10),
            for (final g in app.groups)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: GhostButton(
                  label: '${g.s('emoji')}  ${g.s('name')} · ${l.splitEqual}',
                  onTap: () async {
                    Navigator.of(ctx).pop();
                    await ref.read(appProvider.notifier).send('POST', '/v1/groups/${g.s('id')}/expenses', {
                      'amount_paise': t.paise('amount'),
                      'description': t.s('merchant'),
                      'split_method': 'equal',
                      'category_id': t.s('category_id'),
                      'linked_transaction_id': t.s('id'),
                    });
                    await ref.read(appProvider.notifier).sync();
                  },
                ),
              ),
          ],
        ],
      ),
    );
  }

  void _addCash(BuildContext context) {
    final l = L.of(context);
    showPocketSheet<void>(context, title: l.addCash, builder: (ctx) => _CashForm(categories: ref.read(appProvider).categories.where((c) => c.s('kind') == 'expense').toList()));
  }
}

class _CashForm extends ConsumerStatefulWidget {
  const _CashForm({required this.categories});
  final List<Json> categories;

  @override
  ConsumerState<_CashForm> createState() => _CashFormState();
}

class _CashFormState extends ConsumerState<_CashForm> {
  final _amount = TextEditingController();
  final _what = TextEditingController();
  String _category = 'other_expense';
  bool _busy = false;

  @override
  void dispose() {
    _amount.dispose();
    _what.dispose();
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
        const SizedBox(height: 12),
        TextField(controller: _what, style: Pk.text(15.5), decoration: InputDecoration(labelText: l.whatWasIt)),
        const SizedBox(height: 14),
        Text(l.category.toUpperCase(), style: Pk.label()),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: [for (final c in widget.categories.take(14)) PChip(label: '${c.s('emoji')} ${c.s('name')}', selected: _category == c.s('id'), onTap: () => setState(() => _category = c.s('id')))],
        ),
        const SizedBox(height: 18),
        BlockButton(
          label: paise == null ? l.add : '${l.add} ${displayPaise(paise)}',
          busy: _busy,
          onTap: paise == null || paise <= 0
              ? null
              : () async {
                  setState(() => _busy = true);
                  await ref.read(appProvider.notifier).addTransaction({'amount_paise': paise, 'direction': 'debit', 'category_id': _category, 'description': _what.text.trim()});
                  if (context.mounted) Navigator.of(context).pop();
                },
        ),
      ],
    );
  }
}

class _Accounts extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final accounts = ref.watch(appProvider.select((s) => s.accounts));
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(Pk.pad, 8, Pk.pad, 120),
      itemCount: accounts.length,
      separatorBuilder: (_, _) => const SizedBox(height: Pk.gap),
      itemBuilder: (context, i) {
        final a = accounts[i];
        final card = a.s('type') == 'credit_card';
        return Rise(
          index: i,
          child: PCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(child: Text('${a.s('code')} ·· ${a.s('last4')}'.toUpperCase(), style: Pk.label())),
                    Tag(a.s('type').replaceAll('_', ' '), color: card ? Pk.amber : Pk.muted),
                  ],
                ),
                const SizedBox(height: 10),
                Text(a.sn('nickname') ?? a.s('institution'), style: Pk.text(15.5, w: FontWeight.w500)),
                const SizedBox(height: 6),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Expanded(child: Text(a.money('balance'), style: Pk.num(26, c: card ? Pk.coral : Pk.bone, ls: -0.5))),
                    if (card) Text('${l.limitLabel} ${a.money('credit_limit')}', style: Pk.num(12, c: Pk.faint, w: FontWeight.w400)),
                  ],
                ),
                if (card) ...[
                  const SizedBox(height: 10),
                  SegBar(pct: a.i('used_pct'), color: a.i('used_pct') > 60 ? Pk.coral : Pk.amber, height: 8),
                  const SizedBox(height: 6),
                  Text(l.owedOnCard.toUpperCase(), style: Pk.label(c: Pk.faint, size: 9.5)),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Bills extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final bills = ref.watch(appProvider.select((s) => s.summary.m('bills')));
    final loans = ref.watch(fetchProvider('/v1/loans'));
    return ListView(
      padding: const EdgeInsets.fromLTRB(Pk.pad, 8, Pk.pad, 120),
      children: [
        PCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionLabel(l.segBills, trailing: Text(bills.money('total_due'), style: Pk.num(14))),
              const SizedBox(height: 10),
              BillRows(items: bills.l('upcoming')),
            ],
          ),
        ),
        const SizedBox(height: Pk.gap),
        ...loans.maybeWhen(
          data: (d) => [
            for (final ln in d.l('loans'))
              Padding(
                padding: const EdgeInsets.only(bottom: Pk.gap),
                child: PCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(child: Text(ln.s('lender'), style: Pk.text(15.5, w: FontWeight.w500))),
                          Tag(ln.s('rate_type'), color: Pk.muted),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(l.outstanding.toUpperCase(), style: Pk.label(c: Pk.faint, size: 9.5)),
                                Text(ln.money('outstanding'), style: Pk.num(22, ls: -0.4)),
                              ],
                            ),
                          ),
                          Text('${ln.money('emi')} · ${l.emisLeft(ln.i('months_left'))}', style: Pk.num(12.5, c: Pk.muted, w: FontWeight.w400)),
                        ],
                      ),
                      const SizedBox(height: 10),
                      SegBar(pct: ln.i('paid_pct'), color: Pk.sage, height: 8),
                    ],
                  ),
                ),
              ),
          ],
          orElse: () => const <Widget>[],
        ),
      ],
    );
  }
}

class _Investments extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final inv = ref.watch(appProvider.select((s) => s.summary.m('investments')));
    final holdings = inv.l('holdings');
    if (holdings.isEmpty) return Center(child: StateNote(icon: Icons.show_chart, title: l.noInvestments));
    return ListView(
      padding: const EdgeInsets.fromLTRB(Pk.pad, 8, Pk.pad, 120),
      children: [
        PCard(child: InvestmentsBlock(data: inv, maxItems: 0)),
        const SizedBox(height: Pk.gap),
        for (final h in holdings)
          Padding(
            padding: const EdgeInsets.only(bottom: Pk.gap),
            child: PCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [Expanded(child: Text(h.s('kind').replaceAll('_', ' ').toUpperCase(), style: Pk.label())), if (h.b('approx')) Tag(l.approx, color: Pk.amber)]),
                  const SizedBox(height: 8),
                  Text(h.s('name'), style: Pk.text(15, w: FontWeight.w500, h: 1.3)),
                  const SizedBox(height: 8),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Expanded(child: Text(h.b('approx') && h.paise('value') == 0 ? h.s('detail') : h.money('value'), style: Pk.num(20, ls: -0.3))),
                      if (h['week_change'] is Map)
                        Text('${h.paise('week_change') >= 0 ? '▲' : '▼'} ${h.money('week_change').replaceFirst('-', '')}', style: Pk.num(13, c: h.paise('week_change') >= 0 ? Pk.lime : Pk.coral)),
                    ],
                  ),
                  if (h.paise('invested') > 0 && h.s('kind') == 'mutual_fund')
                    Padding(padding: const EdgeInsets.only(top: 4), child: Text('${l.invested} ${h.money('invested')}', style: Pk.num(12, c: Pk.faint, w: FontWeight.w400))),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
