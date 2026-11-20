/// The A2UI contract between the backend (which builds the messages) and this app (which
/// renders them). Plain values only: the A2UI packages themselves are used in one file,
/// `a2ui_home_renderer.dart`.
///
/// The same values live in `packages/pocket_common/pocket_common/a2ui.py`; the shared fixture
/// `data/fixtures/a2ui_home.json` and the tests on both sides keep them equal.
abstract final class A2uiContract {
  /// Wire versions this build can read. `a2ui_core` 0.8.0 speaks v0.9, v0.9.1 and 1.0; Pocket
  /// only ever emits 1.0, so that is all the app accepts.
  static const supportedProtocolVersions = {'1.0'};

  /// The Pocket Home catalog this build implements. A layout built for another catalog (or a
  /// later version of this one) is not drawn through A2UI: the app falls back to the LayoutSpec.
  static const catalogId = 'https://pocket.in/a2ui/catalogs/home/v1';

  static const surfaceId = 'home';
  static const rootComponent = 'PocketHomeColumn';

  /// A2UI component name -> catalog widget type.
  static const componentTypes = {
    'SafeToSpend': 'safe_to_spend',
    'Pockets': 'pockets',
    'Goals': 'goals',
    'SpendByCategory': 'spend_by_category',
    'CashFlow': 'cash_flow',
    'Transactions': 'transactions',
    'BillsEmis': 'bills_emis',
    'NetWorth': 'net_worth',
    'Investments': 'investments',
    'InsightCard': 'insight_card',
    'PulseCard': 'pulse_card',
    'GroupPot': 'group_pot',
  };

  /// The layout-only props each component accepts besides `variant` and `reason`
  /// (camelCase on the wire) and their JSON type. No component takes a money value.
  static const componentParams = <String, Map<String, String>>{
    'SafeToSpend': {},
    'Pockets': {'maxItems': 'integer', 'sort': 'string'},
    'Goals': {'maxItems': 'integer', 'goalId': 'string'},
    'SpendByCategory': {'period': 'string', 'chart': 'string', 'topN': 'integer'},
    'CashFlow': {'period': 'string', 'span': 'string'},
    'Transactions': {'maxItems': 'integer', 'categoryId': 'string'},
    'BillsEmis': {'windowDays': 'integer'},
    'NetWorth': {},
    'Investments': {'maxItems': 'integer'},
    'InsightCard': {'insightType': 'string'},
    'PulseCard': {'maxItems': 'integer'},
    'GroupPot': {'groupId': 'string'},
  };
}
