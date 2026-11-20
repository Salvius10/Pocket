import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:pocket/app.dart';
import 'package:pocket/core/json.dart';
import 'package:pocket/features/report/report_screen.dart';
import 'package:pocket/l10n/app_localizations.dart';

/// The monthly report laid out at phone width, in each language, from one server answer.
/// The screen adds nothing up: what it shows is what `GET /v1/reports/monthly` sent.
Json money(String display) => {'paise': 1, 'display': display, 'exact': '$display.00', 'spoken': display};

Json answer({bool positive = true, bool hasPrevious = true}) => {
      'month': '2026-10',
      'month_label': 'October 2026',
      'previous_month': '2026-09',
      'previous_label': 'September',
      'has_previous': hasPrevious,
      'income': money('₹67,215'),
      'spend': money('₹60,575'),
      'committed': money('₹22,686'),
      'flexible': money('₹37,889'),
      'saved': money('₹5,000'),
      'net': money(positive ? '₹1,640' : '-₹12,34,567'),
      'net_abs': money(positive ? '₹1,640' : '₹12,34,567'),
      'net_is_positive': positive,
      'previous_spend': money('₹77,526'),
      'spend_delta': money('₹16,951'),
      'spend_direction': hasPrevious ? 'down' : 'same',
      'spend_delta_pct': hasPrevious ? 22 : null,
      'spend_pct_of_income': 90,
      'saved_pct_of_income': 7,
      'bars': {'month': 78, 'previous': 100},
      'categories': [
        {'category_id': 'rent', 'name': 'Rent', 'emoji': '🏠', 'amount': money('₹16,800'), 'pct': 28},
        {'category_id': 'gifts_donations', 'name': 'Gifts and donations to family and friends', 'emoji': '🎁', 'amount': money('₹3,864'), 'pct': 6},
      ],
      'lines': ['You spent ₹60,575 in October, ₹16,951 less than in September.', '₹1,640 of what came in was left over.', 'Most of it went to Rent.'],
      'months': [
        for (final (k, label) in [('2026-10', 'October'), ('2026-09', 'September'), ('2026-08', 'August'), ('2026-07', 'July'), ('2026-06', 'June'), ('2026-05', 'May')])
          {'month': k, 'label': label},
      ],
    };

Future<void> show(WidgetTester tester, String language, Json report, {ValueChanged<String>? onMonth}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    MaterialApp(
      locale: Locale(language),
      supportedLocales: L.supportedLocales,
      localizationsDelegates: pocketLocalizationsDelegates,
      home: Scaffold(
        body: SingleChildScrollView(padding: const EdgeInsets.all(16), child: ReportBody(report: report, onMonth: onMonth ?? (_) {})),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  for (final language in ['en', 'hi', 'ta']) {
    testWidgets('lays out at phone width in $language', (tester) async {
      await show(tester, language, answer());
      expect(tester.takeException(), isNull);
      expect(find.text('October 2026'), findsOneWidget);
      expect(find.text('You spent ₹60,575 in October, ₹16,951 less than in September.'), findsOneWidget);
      expect(find.text('₹1,640'), findsOneWidget); // what was left over, once: the screen does not repeat or recompute it
      expect(find.text('₹67,215'), findsOneWidget);
      expect(find.text('22%'), findsOneWidget);
    });
  }

  testWidgets('a month that ran short says so, and long figures still fit', (tester) async {
    await show(tester, 'en', answer(positive: false));
    expect(tester.takeException(), isNull);
    expect(find.text('SPENT MORE THAN CAME IN'), findsOneWidget);
    expect(find.text('₹12,34,567'), findsOneWidget);
    expect(find.text('LEFT OVER'), findsNothing);
  });

  testWidgets('the first month shows no comparison', (tester) async {
    await show(tester, 'en', answer(hasPrevious: false));
    expect(tester.takeException(), isNull);
    expect(find.textContaining('AGAINST'), findsNothing);
    expect(find.text('22%'), findsNothing);
  });

  testWidgets('tapping a month asks for that month', (tester) async {
    String? asked;
    await show(tester, 'en', answer(), onMonth: (m) => asked = m);
    await tester.tap(find.text('August'));
    expect(asked, '2026-08');
  });
}
