import 'package:a2ui_core/a2ui_core.dart';
import 'package:json_schema_builder/json_schema_builder.dart' show Schema;

/// The A2UI contract between the backend (which builds the messages) and this app (which
/// renders them). The same values live in `packages/pocket_common/pocket_common/a2ui.py`; the
/// shared fixture `data/fixtures/a2ui_home.json` and the tests on both sides keep them equal.
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
}

Map<String, Object?> _widget(Map<String, Object?> props) => {
      'type': 'object',
      'properties': {
        'variant': {'type': 'string', 'enum': ['default', 'hero', 'compact']},
        'reason': {'type': 'string'},
        ...props,
      },
    };

const _int = {'type': 'integer'};
const _str = {'type': 'string'};

/// The Pocket Home catalog as `a2ui_core` understands it: the root column plus the 12 widgets,
/// with the layout-only props each accepts. No component takes a money value.
Catalog<ComponentApi, FunctionImplementation> pocketHomeCatalog() {
  return Catalog<ComponentApi, FunctionImplementation>(
    id: A2uiContract.catalogId,
    title: 'Pocket Home',
    protocolVersion: A2uiProtocolVersion.v1_0,
    components: [
      ComponentApi(
        name: A2uiContract.rootComponent,
        schema: Schema.fromMap({
          'type': 'object',
          'properties': {
            'children': {r'$ref': r'common_types.json#/$defs/ChildList'},
            'summary': _str,
          },
          'required': ['children'],
        }),
      ),
      ComponentApi(name: 'SafeToSpend', schema: Schema.fromMap(_widget({}))),
      ComponentApi(name: 'Pockets', schema: Schema.fromMap(_widget({'maxItems': _int, 'sort': _str}))),
      ComponentApi(name: 'Goals', schema: Schema.fromMap(_widget({'maxItems': _int, 'goalId': _str}))),
      ComponentApi(name: 'SpendByCategory', schema: Schema.fromMap(_widget({'period': _str, 'chart': _str, 'topN': _int}))),
      ComponentApi(name: 'CashFlow', schema: Schema.fromMap(_widget({'period': _str, 'span': _str}))),
      ComponentApi(name: 'Transactions', schema: Schema.fromMap(_widget({'maxItems': _int, 'categoryId': _str}))),
      ComponentApi(name: 'BillsEmis', schema: Schema.fromMap(_widget({'windowDays': _int}))),
      ComponentApi(name: 'NetWorth', schema: Schema.fromMap(_widget({}))),
      ComponentApi(name: 'Investments', schema: Schema.fromMap(_widget({'maxItems': _int}))),
      ComponentApi(name: 'InsightCard', schema: Schema.fromMap(_widget({'insightType': _str}))),
      ComponentApi(name: 'PulseCard', schema: Schema.fromMap(_widget({'maxItems': _int}))),
      ComponentApi(name: 'GroupPot', schema: Schema.fromMap(_widget({'groupId': _str}))),
    ],
  );
}
