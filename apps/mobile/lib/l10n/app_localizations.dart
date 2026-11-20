import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_hi.dart';
import 'app_localizations_ta.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of L
/// returned by `L.of(context)`.
///
/// Applications need to include `L.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: L.localizationsDelegates,
///   supportedLocales: L.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the L.supportedLocales
/// property.
abstract class L {
  L(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static L of(BuildContext context) {
    return Localizations.of<L>(context, L)!;
  }

  static const LocalizationsDelegate<L> delegate = _LDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('hi'),
    Locale('ta'),
  ];

  /// No description provided for @appName.
  ///
  /// In en, this message translates to:
  /// **'Pocket'**
  String get appName;

  /// No description provided for @tabHome.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get tabHome;

  /// No description provided for @tabMoney.
  ///
  /// In en, this message translates to:
  /// **'Money'**
  String get tabMoney;

  /// No description provided for @tabMascot.
  ///
  /// In en, this message translates to:
  /// **'Poko'**
  String get tabMascot;

  /// No description provided for @tabPlan.
  ///
  /// In en, this message translates to:
  /// **'Plan'**
  String get tabPlan;

  /// No description provided for @tabCollab.
  ///
  /// In en, this message translates to:
  /// **'Collab'**
  String get tabCollab;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get retry;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @confirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirm;

  /// No description provided for @notNow.
  ///
  /// In en, this message translates to:
  /// **'Not now'**
  String get notNow;

  /// No description provided for @done.
  ///
  /// In en, this message translates to:
  /// **'Done'**
  String get done;

  /// No description provided for @save.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// No description provided for @add.
  ///
  /// In en, this message translates to:
  /// **'Add'**
  String get add;

  /// No description provided for @continueLabel.
  ///
  /// In en, this message translates to:
  /// **'Continue'**
  String get continueLabel;

  /// No description provided for @skip.
  ///
  /// In en, this message translates to:
  /// **'Skip'**
  String get skip;

  /// No description provided for @offlineBanner.
  ///
  /// In en, this message translates to:
  /// **'Offline. Showing your numbers as of {time}.'**
  String offlineBanner(String time);

  /// No description provided for @asOf.
  ///
  /// In en, this message translates to:
  /// **'As of {time}'**
  String asOf(String time);

  /// No description provided for @errorTitle.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong'**
  String get errorTitle;

  /// No description provided for @errorBody.
  ///
  /// In en, this message translates to:
  /// **'We couldn\'t load this. Check your connection and try again.'**
  String get errorBody;

  /// No description provided for @onbTagline.
  ///
  /// In en, this message translates to:
  /// **'Money that explains itself.'**
  String get onbTagline;

  /// No description provided for @onbPickLanguage.
  ///
  /// In en, this message translates to:
  /// **'Choose your language'**
  String get onbPickLanguage;

  /// No description provided for @onbLangHint.
  ///
  /// In en, this message translates to:
  /// **'You can change this later in Profile.'**
  String get onbLangHint;

  /// No description provided for @onbTryDemo.
  ///
  /// In en, this message translates to:
  /// **'Try a demo persona'**
  String get onbTryDemo;

  /// No description provided for @onbDemoNote.
  ///
  /// In en, this message translates to:
  /// **'Demo data only. No real bank is connected.'**
  String get onbDemoNote;

  /// No description provided for @onbVoiceTitle.
  ///
  /// In en, this message translates to:
  /// **'Pick Poko\'s voice'**
  String get onbVoiceTitle;

  /// No description provided for @voiceWarm.
  ///
  /// In en, this message translates to:
  /// **'Warm'**
  String get voiceWarm;

  /// No description provided for @voiceBright.
  ///
  /// In en, this message translates to:
  /// **'Bright'**
  String get voiceBright;

  /// No description provided for @voiceCalm.
  ///
  /// In en, this message translates to:
  /// **'Calm'**
  String get voiceCalm;

  /// No description provided for @voiceClear.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get voiceClear;

  /// No description provided for @onbTalkTitle.
  ///
  /// In en, this message translates to:
  /// **'Tell Poko about your money'**
  String get onbTalkTitle;

  /// No description provided for @onbTalkHint.
  ///
  /// In en, this message translates to:
  /// **'Four quick questions. Type or talk.'**
  String get onbTalkHint;

  /// No description provided for @onbSkipTalk.
  ///
  /// In en, this message translates to:
  /// **'Skip the chat'**
  String get onbSkipTalk;

  /// No description provided for @onbPickPersona.
  ///
  /// In en, this message translates to:
  /// **'Pick the profile closest to you'**
  String get onbPickPersona;

  /// No description provided for @onbPersonaNote.
  ///
  /// In en, this message translates to:
  /// **'Each one is invented, with a year of realistic money.'**
  String get onbPersonaNote;

  /// No description provided for @onbSuggested.
  ///
  /// In en, this message translates to:
  /// **'Closest match'**
  String get onbSuggested;

  /// No description provided for @onbBuild.
  ///
  /// In en, this message translates to:
  /// **'Build my Home'**
  String get onbBuild;

  /// No description provided for @onbBuilding.
  ///
  /// In en, this message translates to:
  /// **'Building your Home'**
  String get onbBuilding;

  /// No description provided for @onbStep.
  ///
  /// In en, this message translates to:
  /// **'Step {n} of {total}'**
  String onbStep(int n, int total);

  /// No description provided for @greetMorning.
  ///
  /// In en, this message translates to:
  /// **'Good morning'**
  String get greetMorning;

  /// No description provided for @greetAfternoon.
  ///
  /// In en, this message translates to:
  /// **'Good afternoon'**
  String get greetAfternoon;

  /// No description provided for @greetEvening.
  ///
  /// In en, this message translates to:
  /// **'Good evening'**
  String get greetEvening;

  /// No description provided for @safeToSpend.
  ///
  /// In en, this message translates to:
  /// **'Safe to spend today'**
  String get safeToSpend;

  /// No description provided for @perDay.
  ///
  /// In en, this message translates to:
  /// **'a day'**
  String get perDay;

  /// No description provided for @leftToday.
  ///
  /// In en, this message translates to:
  /// **'Left today'**
  String get leftToday;

  /// No description provided for @spentToday.
  ///
  /// In en, this message translates to:
  /// **'Spent today'**
  String get spentToday;

  /// No description provided for @daysLeft.
  ///
  /// In en, this message translates to:
  /// **'{n} days left'**
  String daysLeft(int n);

  /// No description provided for @overToday.
  ///
  /// In en, this message translates to:
  /// **'Over today\'s amount by {amount}'**
  String overToday(String amount);

  /// No description provided for @nothingLeft.
  ///
  /// In en, this message translates to:
  /// **'Nothing left to spend freely this month'**
  String get nothingLeft;

  /// No description provided for @stsIncome.
  ///
  /// In en, this message translates to:
  /// **'Income'**
  String get stsIncome;

  /// No description provided for @stsCommitted.
  ///
  /// In en, this message translates to:
  /// **'Bills & EMIs'**
  String get stsCommitted;

  /// No description provided for @stsGoals.
  ///
  /// In en, this message translates to:
  /// **'Goals'**
  String get stsGoals;

  /// No description provided for @stsSpent.
  ///
  /// In en, this message translates to:
  /// **'Spent'**
  String get stsSpent;

  /// No description provided for @stsFormula.
  ///
  /// In en, this message translates to:
  /// **'Income, minus bills and goals, minus what you\'ve spent, shared over the days left.'**
  String get stsFormula;

  /// No description provided for @wPockets.
  ///
  /// In en, this message translates to:
  /// **'Pockets'**
  String get wPockets;

  /// No description provided for @wGoals.
  ///
  /// In en, this message translates to:
  /// **'Goals'**
  String get wGoals;

  /// No description provided for @wSpend.
  ///
  /// In en, this message translates to:
  /// **'Where it goes'**
  String get wSpend;

  /// No description provided for @wCashFlow.
  ///
  /// In en, this message translates to:
  /// **'Cash flow'**
  String get wCashFlow;

  /// No description provided for @wTransactions.
  ///
  /// In en, this message translates to:
  /// **'Recent'**
  String get wTransactions;

  /// No description provided for @wBills.
  ///
  /// In en, this message translates to:
  /// **'Bills & EMIs'**
  String get wBills;

  /// No description provided for @wNetWorth.
  ///
  /// In en, this message translates to:
  /// **'Net worth'**
  String get wNetWorth;

  /// No description provided for @wInvestments.
  ///
  /// In en, this message translates to:
  /// **'Investments'**
  String get wInvestments;

  /// No description provided for @wInsight.
  ///
  /// In en, this message translates to:
  /// **'Noticed'**
  String get wInsight;

  /// No description provided for @wPulse.
  ///
  /// In en, this message translates to:
  /// **'Pulse'**
  String get wPulse;

  /// No description provided for @wGroup.
  ///
  /// In en, this message translates to:
  /// **'Group'**
  String get wGroup;

  /// No description provided for @whyLayout.
  ///
  /// In en, this message translates to:
  /// **'Why this layout?'**
  String get whyLayout;

  /// No description provided for @whyLayoutTitle.
  ///
  /// In en, this message translates to:
  /// **'Why your Home looks like this'**
  String get whyLayoutTitle;

  /// No description provided for @editHome.
  ///
  /// In en, this message translates to:
  /// **'Edit Home'**
  String get editHome;

  /// No description provided for @editHomeHint.
  ///
  /// In en, this message translates to:
  /// **'Drag to reorder. Safe-to-spend stays on top.'**
  String get editHomeHint;

  /// No description provided for @resetHome.
  ///
  /// In en, this message translates to:
  /// **'Reset to Poko\'s layout'**
  String get resetHome;

  /// No description provided for @askPokoChange.
  ///
  /// In en, this message translates to:
  /// **'Ask Poko to change it'**
  String get askPokoChange;

  /// No description provided for @homeSaved.
  ///
  /// In en, this message translates to:
  /// **'Home saved'**
  String get homeSaved;

  /// No description provided for @ofLimit.
  ///
  /// In en, this message translates to:
  /// **'of {limit}'**
  String ofLimit(String limit);

  /// No description provided for @leftLabel.
  ///
  /// In en, this message translates to:
  /// **'{amount} left'**
  String leftLabel(String amount);

  /// No description provided for @overLabel.
  ///
  /// In en, this message translates to:
  /// **'{amount} over'**
  String overLabel(String amount);

  /// No description provided for @statusOver.
  ///
  /// In en, this message translates to:
  /// **'Over'**
  String get statusOver;

  /// No description provided for @statusWatch.
  ///
  /// In en, this message translates to:
  /// **'Watch'**
  String get statusWatch;

  /// No description provided for @statusOk.
  ///
  /// In en, this message translates to:
  /// **'On track'**
  String get statusOk;

  /// No description provided for @statusBehind.
  ///
  /// In en, this message translates to:
  /// **'Behind'**
  String get statusBehind;

  /// No description provided for @statusReached.
  ///
  /// In en, this message translates to:
  /// **'Reached'**
  String get statusReached;

  /// No description provided for @statusPaused.
  ///
  /// In en, this message translates to:
  /// **'Paused'**
  String get statusPaused;

  /// No description provided for @thisMonth.
  ///
  /// In en, this message translates to:
  /// **'This month'**
  String get thisMonth;

  /// No description provided for @income.
  ///
  /// In en, this message translates to:
  /// **'In'**
  String get income;

  /// No description provided for @spend.
  ///
  /// In en, this message translates to:
  /// **'Out'**
  String get spend;

  /// No description provided for @dueIn.
  ///
  /// In en, this message translates to:
  /// **'in {n} days'**
  String dueIn(int n);

  /// No description provided for @dueToday.
  ///
  /// In en, this message translates to:
  /// **'today'**
  String get dueToday;

  /// No description provided for @dueTomorrow.
  ///
  /// In en, this message translates to:
  /// **'tomorrow'**
  String get dueTomorrow;

  /// No description provided for @overdue.
  ///
  /// In en, this message translates to:
  /// **'overdue'**
  String get overdue;

  /// No description provided for @autopay.
  ///
  /// In en, this message translates to:
  /// **'Auto'**
  String get autopay;

  /// No description provided for @assets.
  ///
  /// In en, this message translates to:
  /// **'You have'**
  String get assets;

  /// No description provided for @liabilities.
  ///
  /// In en, this message translates to:
  /// **'You owe'**
  String get liabilities;

  /// No description provided for @weekChange.
  ///
  /// In en, this message translates to:
  /// **'This week'**
  String get weekChange;

  /// No description provided for @viewOnly.
  ///
  /// In en, this message translates to:
  /// **'View only. Pocket never asks you to buy or sell.'**
  String get viewOnly;

  /// No description provided for @noInsights.
  ///
  /// In en, this message translates to:
  /// **'Nothing new to flag'**
  String get noInsights;

  /// No description provided for @noInsightsBody.
  ///
  /// In en, this message translates to:
  /// **'Poko is watching. Patterns will show up here.'**
  String get noInsightsBody;

  /// No description provided for @forYou.
  ///
  /// In en, this message translates to:
  /// **'For you'**
  String get forYou;

  /// No description provided for @youOwe.
  ///
  /// In en, this message translates to:
  /// **'You owe {amount}'**
  String youOwe(String amount);

  /// No description provided for @youAreOwed.
  ///
  /// In en, this message translates to:
  /// **'You are owed {amount}'**
  String youAreOwed(String amount);

  /// No description provided for @allSettled.
  ///
  /// In en, this message translates to:
  /// **'All settled'**
  String get allSettled;

  /// No description provided for @dismiss.
  ///
  /// In en, this message translates to:
  /// **'Dismiss'**
  String get dismiss;

  /// No description provided for @moneyTitle.
  ///
  /// In en, this message translates to:
  /// **'Money'**
  String get moneyTitle;

  /// No description provided for @segTransactions.
  ///
  /// In en, this message translates to:
  /// **'Transactions'**
  String get segTransactions;

  /// No description provided for @segAccounts.
  ///
  /// In en, this message translates to:
  /// **'Accounts'**
  String get segAccounts;

  /// No description provided for @segBills.
  ///
  /// In en, this message translates to:
  /// **'Bills & EMIs'**
  String get segBills;

  /// No description provided for @segInvestments.
  ///
  /// In en, this message translates to:
  /// **'Investments'**
  String get segInvestments;

  /// No description provided for @searchHint.
  ///
  /// In en, this message translates to:
  /// **'Search merchant or note'**
  String get searchHint;

  /// No description provided for @filterAll.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get filterAll;

  /// No description provided for @filterOut.
  ///
  /// In en, this message translates to:
  /// **'Spent'**
  String get filterOut;

  /// No description provided for @filterIn.
  ///
  /// In en, this message translates to:
  /// **'Received'**
  String get filterIn;

  /// No description provided for @addCash.
  ///
  /// In en, this message translates to:
  /// **'Add cash entry'**
  String get addCash;

  /// No description provided for @amountRupees.
  ///
  /// In en, this message translates to:
  /// **'Amount (₹)'**
  String get amountRupees;

  /// No description provided for @whatWasIt.
  ///
  /// In en, this message translates to:
  /// **'What was it?'**
  String get whatWasIt;

  /// No description provided for @category.
  ///
  /// In en, this message translates to:
  /// **'Category'**
  String get category;

  /// No description provided for @changeCategory.
  ///
  /// In en, this message translates to:
  /// **'Change category'**
  String get changeCategory;

  /// No description provided for @splitWithGroup.
  ///
  /// In en, this message translates to:
  /// **'Split with a group'**
  String get splitWithGroup;

  /// No description provided for @noTransactions.
  ///
  /// In en, this message translates to:
  /// **'No transactions found'**
  String get noTransactions;

  /// No description provided for @owedOnCard.
  ///
  /// In en, this message translates to:
  /// **'Owed'**
  String get owedOnCard;

  /// No description provided for @limitLabel.
  ///
  /// In en, this message translates to:
  /// **'Limit'**
  String get limitLabel;

  /// No description provided for @emisLeft.
  ///
  /// In en, this message translates to:
  /// **'{n} EMIs left'**
  String emisLeft(int n);

  /// No description provided for @outstanding.
  ///
  /// In en, this message translates to:
  /// **'Outstanding'**
  String get outstanding;

  /// No description provided for @invested.
  ///
  /// In en, this message translates to:
  /// **'Invested'**
  String get invested;

  /// No description provided for @approx.
  ///
  /// In en, this message translates to:
  /// **'approx.'**
  String get approx;

  /// No description provided for @noBills.
  ///
  /// In en, this message translates to:
  /// **'Nothing due soon'**
  String get noBills;

  /// No description provided for @noInvestments.
  ///
  /// In en, this message translates to:
  /// **'No investments linked'**
  String get noInvestments;

  /// No description provided for @mascotTalk.
  ///
  /// In en, this message translates to:
  /// **'Talk'**
  String get mascotTalk;

  /// No description provided for @mascotNoticed.
  ///
  /// In en, this message translates to:
  /// **'Noticed'**
  String get mascotNoticed;

  /// No description provided for @mascotPulse.
  ///
  /// In en, this message translates to:
  /// **'Pulse'**
  String get mascotPulse;

  /// No description provided for @typeHint.
  ///
  /// In en, this message translates to:
  /// **'Ask about your money'**
  String get typeHint;

  /// No description provided for @micStart.
  ///
  /// In en, this message translates to:
  /// **'Tap to talk'**
  String get micStart;

  /// No description provided for @micStop.
  ///
  /// In en, this message translates to:
  /// **'Tap to stop'**
  String get micStop;

  /// No description provided for @connecting.
  ///
  /// In en, this message translates to:
  /// **'Connecting'**
  String get connecting;

  /// No description provided for @voiceOffNote.
  ///
  /// In en, this message translates to:
  /// **'Voice comes on when the live key is set. Type to chat.'**
  String get voiceOffNote;

  /// No description provided for @mascotOffline.
  ///
  /// In en, this message translates to:
  /// **'Poko needs the internet. Your numbers are still here.'**
  String get mascotOffline;

  /// No description provided for @confirmCardNote.
  ///
  /// In en, this message translates to:
  /// **'Nothing happens until you tap Confirm.'**
  String get confirmCardNote;

  /// No description provided for @proposalDone.
  ///
  /// In en, this message translates to:
  /// **'Done. Your numbers are updated.'**
  String get proposalDone;

  /// No description provided for @proposalFailed.
  ///
  /// In en, this message translates to:
  /// **'That couldn\'t be done. Nothing was changed.'**
  String get proposalFailed;

  /// No description provided for @promptToday.
  ///
  /// In en, this message translates to:
  /// **'How much can I spend today?'**
  String get promptToday;

  /// No description provided for @promptSpend.
  ///
  /// In en, this message translates to:
  /// **'Where is my money going?'**
  String get promptSpend;

  /// No description provided for @promptNotice.
  ///
  /// In en, this message translates to:
  /// **'What did you notice?'**
  String get promptNotice;

  /// No description provided for @promptFund.
  ///
  /// In en, this message translates to:
  /// **'Should I buy this fund?'**
  String get promptFund;

  /// No description provided for @promptBills.
  ///
  /// In en, this message translates to:
  /// **'Put my bills first'**
  String get promptBills;

  /// No description provided for @pulseEmpty.
  ///
  /// In en, this message translates to:
  /// **'No Pulse yet today'**
  String get pulseEmpty;

  /// No description provided for @pulseEmptyBody.
  ///
  /// In en, this message translates to:
  /// **'Markets and world news with sources will appear here.'**
  String get pulseEmptyBody;

  /// No description provided for @planTitle.
  ///
  /// In en, this message translates to:
  /// **'Plan'**
  String get planTitle;

  /// No description provided for @suggested.
  ///
  /// In en, this message translates to:
  /// **'Suggested moves'**
  String get suggested;

  /// No description provided for @newPocket.
  ///
  /// In en, this message translates to:
  /// **'New pocket'**
  String get newPocket;

  /// No description provided for @newGoal.
  ///
  /// In en, this message translates to:
  /// **'New goal'**
  String get newGoal;

  /// No description provided for @nameLabel.
  ///
  /// In en, this message translates to:
  /// **'Name'**
  String get nameLabel;

  /// No description provided for @monthlyLimit.
  ///
  /// In en, this message translates to:
  /// **'Monthly limit (₹)'**
  String get monthlyLimit;

  /// No description provided for @targetAmount.
  ///
  /// In en, this message translates to:
  /// **'Target (₹)'**
  String get targetAmount;

  /// No description provided for @pausePocket.
  ///
  /// In en, this message translates to:
  /// **'Pause'**
  String get pausePocket;

  /// No description provided for @resumePocket.
  ///
  /// In en, this message translates to:
  /// **'Resume'**
  String get resumePocket;

  /// No description provided for @needPerMonth.
  ///
  /// In en, this message translates to:
  /// **'Needs {amount} a month'**
  String needPerMonth(String amount);

  /// No description provided for @byDate.
  ///
  /// In en, this message translates to:
  /// **'by {date}'**
  String byDate(String date);

  /// No description provided for @noPockets.
  ///
  /// In en, this message translates to:
  /// **'No pockets yet'**
  String get noPockets;

  /// No description provided for @noGoals.
  ///
  /// In en, this message translates to:
  /// **'No goals yet'**
  String get noGoals;

  /// No description provided for @collabTitle.
  ///
  /// In en, this message translates to:
  /// **'Collab'**
  String get collabTitle;

  /// No description provided for @newGroup.
  ///
  /// In en, this message translates to:
  /// **'New group'**
  String get newGroup;

  /// No description provided for @joinGroup.
  ///
  /// In en, this message translates to:
  /// **'Join with a code'**
  String get joinGroup;

  /// No description provided for @inviteCode.
  ///
  /// In en, this message translates to:
  /// **'Invite code'**
  String get inviteCode;

  /// No description provided for @groupName.
  ///
  /// In en, this message translates to:
  /// **'Group name'**
  String get groupName;

  /// No description provided for @typeFamily.
  ///
  /// In en, this message translates to:
  /// **'Family'**
  String get typeFamily;

  /// No description provided for @typeTrip.
  ///
  /// In en, this message translates to:
  /// **'Trip'**
  String get typeTrip;

  /// No description provided for @typeFlatmates.
  ///
  /// In en, this message translates to:
  /// **'Flatmates'**
  String get typeFlatmates;

  /// No description provided for @typeCustom.
  ///
  /// In en, this message translates to:
  /// **'Custom'**
  String get typeCustom;

  /// No description provided for @members.
  ///
  /// In en, this message translates to:
  /// **'Members'**
  String get members;

  /// No description provided for @expenses.
  ///
  /// In en, this message translates to:
  /// **'Expenses'**
  String get expenses;

  /// No description provided for @settleUp.
  ///
  /// In en, this message translates to:
  /// **'Settle up'**
  String get settleUp;

  /// No description provided for @addExpense.
  ///
  /// In en, this message translates to:
  /// **'Add expense'**
  String get addExpense;

  /// No description provided for @paidBy.
  ///
  /// In en, this message translates to:
  /// **'Paid by'**
  String get paidBy;

  /// No description provided for @splitEqual.
  ///
  /// In en, this message translates to:
  /// **'Split equally'**
  String get splitEqual;

  /// No description provided for @addGuest.
  ///
  /// In en, this message translates to:
  /// **'Add a guest'**
  String get addGuest;

  /// No description provided for @guestUpi.
  ///
  /// In en, this message translates to:
  /// **'UPI ID (optional)'**
  String get guestUpi;

  /// No description provided for @payByUpi.
  ///
  /// In en, this message translates to:
  /// **'Pay by UPI'**
  String get payByUpi;

  /// No description provided for @openUpiApp.
  ///
  /// In en, this message translates to:
  /// **'Open UPI app'**
  String get openUpiApp;

  /// No description provided for @copyUpiId.
  ///
  /// In en, this message translates to:
  /// **'Copy UPI ID'**
  String get copyUpiId;

  /// No description provided for @copied.
  ///
  /// In en, this message translates to:
  /// **'Copied'**
  String get copied;

  /// No description provided for @markPaid.
  ///
  /// In en, this message translates to:
  /// **'I\'ve paid'**
  String get markPaid;

  /// No description provided for @confirmReceived.
  ///
  /// In en, this message translates to:
  /// **'Confirm received'**
  String get confirmReceived;

  /// No description provided for @pays.
  ///
  /// In en, this message translates to:
  /// **'{from} pays {to}'**
  String pays(String from, String to);

  /// No description provided for @pocketNeverHolds.
  ///
  /// In en, this message translates to:
  /// **'Pocket never holds money. You pay in your own UPI app.'**
  String get pocketNeverHolds;

  /// No description provided for @demoUpiNote.
  ///
  /// In en, this message translates to:
  /// **'Demo UPI IDs (@pocketdemo) are not real, so no money will move.'**
  String get demoUpiNote;

  /// No description provided for @sharedBudget.
  ///
  /// In en, this message translates to:
  /// **'Shared budget'**
  String get sharedBudget;

  /// No description provided for @pot.
  ///
  /// In en, this message translates to:
  /// **'Pot'**
  String get pot;

  /// No description provided for @addToPot.
  ///
  /// In en, this message translates to:
  /// **'Add to pot'**
  String get addToPot;

  /// No description provided for @privacyGroup.
  ///
  /// In en, this message translates to:
  /// **'What this group sees'**
  String get privacyGroup;

  /// No description provided for @privacyGroupNote.
  ///
  /// In en, this message translates to:
  /// **'Nothing of yours is shared unless you turn it on.'**
  String get privacyGroupNote;

  /// No description provided for @shareNothing.
  ///
  /// In en, this message translates to:
  /// **'Sharing nothing'**
  String get shareNothing;

  /// No description provided for @noGroups.
  ///
  /// In en, this message translates to:
  /// **'No groups yet'**
  String get noGroups;

  /// No description provided for @noGroupsBody.
  ///
  /// In en, this message translates to:
  /// **'Start one for a trip, your flat or your family.'**
  String get noGroupsBody;

  /// No description provided for @you.
  ///
  /// In en, this message translates to:
  /// **'You'**
  String get you;

  /// No description provided for @guest.
  ///
  /// In en, this message translates to:
  /// **'Guest'**
  String get guest;

  /// No description provided for @statusPending.
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get statusPending;

  /// No description provided for @statusLinkOpened.
  ///
  /// In en, this message translates to:
  /// **'Link opened'**
  String get statusLinkOpened;

  /// No description provided for @statusMarkedPaid.
  ///
  /// In en, this message translates to:
  /// **'Marked paid'**
  String get statusMarkedPaid;

  /// No description provided for @statusConfirmed.
  ///
  /// In en, this message translates to:
  /// **'Confirmed'**
  String get statusConfirmed;

  /// No description provided for @yourShare.
  ///
  /// In en, this message translates to:
  /// **'Your share {amount}'**
  String yourShare(String amount);

  /// No description provided for @membersCount.
  ///
  /// In en, this message translates to:
  /// **'{n} members'**
  String membersCount(int n);

  /// No description provided for @profileTitle.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get profileTitle;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// No description provided for @mascotVoice.
  ///
  /// In en, this message translates to:
  /// **'Poko\'s voice'**
  String get mascotVoice;

  /// No description provided for @nudgesTitle.
  ///
  /// In en, this message translates to:
  /// **'Nudges'**
  String get nudgesTitle;

  /// No description provided for @nudgesPerDay.
  ///
  /// In en, this message translates to:
  /// **'Nudges a day'**
  String get nudgesPerDay;

  /// No description provided for @quietHours.
  ///
  /// In en, this message translates to:
  /// **'Quiet hours'**
  String get quietHours;

  /// No description provided for @privacy.
  ///
  /// In en, this message translates to:
  /// **'Privacy'**
  String get privacy;

  /// No description provided for @exportData.
  ///
  /// In en, this message translates to:
  /// **'Export my data'**
  String get exportData;

  /// No description provided for @deleteData.
  ///
  /// In en, this message translates to:
  /// **'Delete my data'**
  String get deleteData;

  /// No description provided for @deleteConfirm.
  ///
  /// In en, this message translates to:
  /// **'This removes everything about you from Pocket. It can\'t be undone.'**
  String get deleteConfirm;

  /// No description provided for @disclaimerTitle.
  ///
  /// In en, this message translates to:
  /// **'Data, not advice'**
  String get disclaimerTitle;

  /// No description provided for @disclaimerBody.
  ///
  /// In en, this message translates to:
  /// **'Pocket shows your own numbers and general explanations. It never tells you to buy, sell or switch any investment. All data in this build is synthetic.'**
  String get disclaimerBody;

  /// No description provided for @switchPersona.
  ///
  /// In en, this message translates to:
  /// **'Switch demo profile'**
  String get switchPersona;

  /// No description provided for @demoTools.
  ///
  /// In en, this message translates to:
  /// **'Demo tools'**
  String get demoTools;

  /// No description provided for @injectSwiggy.
  ///
  /// In en, this message translates to:
  /// **'Add a Swiggy order now'**
  String get injectSwiggy;

  /// No description provided for @linkedAccounts.
  ///
  /// In en, this message translates to:
  /// **'Linked accounts'**
  String get linkedAccounts;

  /// No description provided for @startOver.
  ///
  /// In en, this message translates to:
  /// **'Start over'**
  String get startOver;

  /// No description provided for @exported.
  ///
  /// In en, this message translates to:
  /// **'Export ready: {n} transactions'**
  String exported(int n);

  /// No description provided for @muteVoice.
  ///
  /// In en, this message translates to:
  /// **'Mute voice'**
  String get muteVoice;
}

class _LDelegate extends LocalizationsDelegate<L> {
  const _LDelegate();

  @override
  Future<L> load(Locale locale) {
    return SynchronousFuture<L>(lookupL(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'hi', 'ta'].contains(locale.languageCode);

  @override
  bool shouldReload(_LDelegate old) => false;
}

L lookupL(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return LEn();
    case 'hi':
      return LHi();
    case 'ta':
      return LTa();
  }

  throw FlutterError(
    'L.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
