import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:pocket/app.dart';
import 'package:pocket/core/ui.dart';
import 'package:pocket/l10n/app_localizations.dart';

/// In Hindi and Tamil, Material's own strings (a back button's tooltip, a sheet's close label)
/// must resolve. With the wrong delegates they are null and the whole screen fails to draw:
/// Profile and every bottom sheet did, in exactly those two languages.
void main() {
  for (final language in ['en', 'hi', 'ta']) {
    testWidgets('Material and Pocket strings resolve in $language', (tester) async {
      late BuildContext inside;
      await tester.pumpWidget(
        MaterialApp(
          locale: Locale(language),
          supportedLocales: L.supportedLocales,
          localizationsDelegates: pocketLocalizationsDelegates,
          home: Builder(
            builder: (context) {
              inside = context;
              return Scaffold(
                body: Column(
                  children: [
                    IconButton(onPressed: () {}, icon: const Icon(Icons.arrow_back), tooltip: MaterialLocalizations.of(context).backButtonTooltip),
                    Text(L.of(context).smsTitle),
                    const TextField(),
                  ],
                ),
              );
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(MaterialLocalizations.of(inside).closeButtonLabel, isNotEmpty);
      expect(find.byType(TextField), findsOneWidget);

      // a house-style bottom sheet uses Material's close label too
      showPocketSheet<void>(inside, title: L.of(inside).smsTitle, builder: (_) => Text(L.of(inside).smsSynthetic));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text(L.of(inside).smsSynthetic), findsOneWidget);
    });
  }
}
