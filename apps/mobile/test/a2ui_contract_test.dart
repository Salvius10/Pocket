import 'dart:convert';
import 'dart:io';

import 'package:a2ui_core/a2ui_core.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pocket/core/json.dart';
import 'package:pocket/features/home/renderer/a2ui_contract.dart';
import 'package:pocket/features/home/renderer/a2ui_home_renderer.dart';
import 'package:pocket/features/home/renderer/direct_renderer.dart';

import 'fixtures.dart';

/// Agent side and renderer side must agree on the A2UI version, the catalog and the component
/// names. `data/fixtures/a2ui_home.json` is what the backend builder emits today (a Python test
/// pins that); these tests feed it to the pinned `a2ui_core` and to the app's Home renderer.
void main() {
  final contract = Map<String, dynamic>.from(jsonDecode(File(fixturePath('a2ui_home.json')).readAsStringSync()) as Map);
  final messages = contract.l('messages');
  final spec = contract.m('spec');

  group('versions', () {
    test('the backend emits a protocol version this app accepts', () {
      expect(A2uiContract.supportedProtocolVersions, contains(contract.s('protocol_version')));
      for (final m in messages) {
        expect(m['version'], contract['protocol_version']);
      }
    });

    test('the pinned a2ui_core speaks that version on the wire', () {
      expect(A2uiProtocolVersion.v1_0.jsonValue, contract.s('protocol_version'));
    });

    test('catalog id, root component and component names match on both sides', () {
      expect(contract.s('catalog_id'), A2uiContract.catalogId);
      expect(contract.s('root_component'), A2uiContract.rootComponent);
      final backendNames = Map<String, dynamic>.from(contract['component_names'] as Map);
      expect({for (final e in backendNames.entries) e.value as String: e.key}, A2uiContract.componentTypes);
    });
  });

  group('a2ui_core accepts what the backend builds', () {
    test('MessageProcessor reports no errors and creates the Home surface', () {
      final errors = <String>[];
      final processor = MessageProcessor<ComponentApi>(
        catalogs: [pocketHomeCatalog()],
        defaultVersion: A2uiProtocolVersion.v1_0,
        onError: (e) => errors.add(e.toString()),
      );
      final reported = processor.processMessagesWithErrors(messages);
      expect(reported.map((e) => e.error.toString()).toList(), isEmpty);
      expect(errors, isEmpty);
      expect(processor.model.getSurface(A2uiContract.surfaceId), isNotNull);
      processor.dispose();
    });
  });

  // Note: a2ui_core 0.8.0 does not report an error for a component name outside the catalog when it
  // processes messages. Rejecting unknown widget types is therefore this app's job; the last test
  // below proves the adapter drops them.
  group('the app renders the same Home from A2UI and from the LayoutSpec', () {
    List<String> types(List<HomeEntry> entries) => [for (final e in entries) '${e.type}/${e.variant}/${jsonEncode(e.params)}'];

    test('both renderers give the same widgets, order, params and reasons', () {
      final viaA2ui = renderHome({'spec': <String, dynamic>{}, 'a2ui': messages});
      final direct = renderDirect(spec);
      expect(types(viaA2ui), types(direct));
      expect([for (final e in viaA2ui) e.reason], [for (final e in direct) e.reason]);
      expect(viaA2ui.first.type, 'safe_to_spend');
    });

    test('a newer protocol version falls back to the LayoutSpec instead of guessing', () {
      final future = jsonDecode(jsonEncode(messages).replaceAll('"version":"1.0"', '"version":"2.0"')) as List;
      final check = checkA2ui({'a2ui': future});
      expect(check.ok, isFalse);
      expect(check.reason, contains('protocol version'));
      expect(types(renderHome({'spec': spec, 'a2ui': future})), types(renderDirect(spec)));
    });

    test('a different catalog falls back to the LayoutSpec', () {
      final other = jsonDecode(jsonEncode(messages).replaceAll('/home/v1', '/home/v2')) as List;
      final check = checkA2ui({'a2ui': other});
      expect(check.ok, isFalse);
      expect(check.reason, contains('catalog'));
      expect(types(renderHome({'spec': spec, 'a2ui': other})), types(renderDirect(spec)));
    });

    test('an unknown component is dropped, never drawn', () {
      final tampered = jsonDecode(jsonEncode(messages)) as List;
      ((tampered[1] as Map)['updateComponents']['components'] as List).add({'id': 'x', 'component': 'CryptoTicker'});
      (((tampered[1] as Map)['updateComponents']['components'] as List).first as Map)['children'].add('x');
      final entries = renderHome({'spec': spec, 'a2ui': tampered});
      expect(entries.map((e) => e.type), isNot(contains('CryptoTicker')));
      expect(entries.length, renderDirect(spec).length);
    });
  });
}
