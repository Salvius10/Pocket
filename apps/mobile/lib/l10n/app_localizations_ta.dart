// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Tamil (`ta`).
class LTa extends L {
  LTa([String locale = 'ta']) : super(locale);

  @override
  String get appName => 'பாக்கெட்';

  @override
  String get tabHome => 'முகப்பு';

  @override
  String get tabMoney => 'பணம்';

  @override
  String get tabMascot => 'போகோ';

  @override
  String get tabPlan => 'திட்டம்';

  @override
  String get tabCollab => 'சேர்ந்து';

  @override
  String get retry => 'மீண்டும் முயற்சி';

  @override
  String get cancel => 'ரத்து';

  @override
  String get confirm => 'உறுதிசெய்';

  @override
  String get notNow => 'இப்போது வேண்டாம்';

  @override
  String get done => 'முடிந்தது';

  @override
  String get save => 'சேமி';

  @override
  String get add => 'சேர்';

  @override
  String get continueLabel => 'தொடர்க';

  @override
  String get skip => 'தவிர்';

  @override
  String offlineBanner(String time) {
    return 'இணைப்பு இல்லை. $time வரையிலான எண்கள் காட்டப்படுகின்றன.';
  }

  @override
  String asOf(String time) {
    return '$time வரை';
  }

  @override
  String get errorTitle => 'ஏதோ தவறு நடந்தது';

  @override
  String get errorBody => 'இதை ஏற்ற முடியவில்லை. இணைப்பைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்.';

  @override
  String get onbTagline => 'தன்னைத் தானே விளக்கும் பணம்.';

  @override
  String get onbPickLanguage => 'உங்கள் மொழியைத் தேர்ந்தெடுங்கள்';

  @override
  String get onbLangHint => 'பின்னர் சுயவிவரத்தில் மாற்றலாம்.';

  @override
  String get onbTryDemo => 'டெமோ சுயவிவரத்தை முயற்சிக்கவும்';

  @override
  String get onbDemoNote => 'டெமோ தரவு மட்டும். உண்மையான வங்கி எதுவும் இணைக்கப்படவில்லை.';

  @override
  String get onbVoiceTitle => 'போகோவின் குரலைத் தேர்ந்தெடுங்கள்';

  @override
  String get voiceWarm => 'இதமான';

  @override
  String get voiceBright => 'உற்சாகமான';

  @override
  String get voiceCalm => 'அமைதியான';

  @override
  String get voiceClear => 'தெளிவான';

  @override
  String get onbTalkTitle => 'உங்கள் பணத்தைப் பற்றி போகோவிடம் சொல்லுங்கள்';

  @override
  String get onbTalkHint => 'நான்கு சிறு கேள்விகள். தட்டச்சு செய்யலாம் அல்லது பேசலாம்.';

  @override
  String get onbSkipTalk => 'உரையாடலைத் தவிர்';

  @override
  String get onbPickPersona => 'உங்களுக்கு மிக நெருக்கமான சுயவிவரத்தைத் தேர்ந்தெடுங்கள்';

  @override
  String get onbPersonaNote => 'ஒவ்வொன்றும் கற்பனையானது; ஒரு வருட நிஜம் போன்ற பணப் பதிவுகளுடன்.';

  @override
  String get onbSuggested => 'மிக நெருக்கம்';

  @override
  String get onbBuild => 'என் முகப்பை அமை';

  @override
  String get onbBuilding => 'உங்கள் முகப்பு அமைகிறது';

  @override
  String onbStep(int n, int total) {
    return 'படி $n / $total';
  }

  @override
  String get greetMorning => 'காலை வணக்கம்';

  @override
  String get greetAfternoon => 'மதிய வணக்கம்';

  @override
  String get greetEvening => 'மாலை வணக்கம்';

  @override
  String get safeToSpend => 'இன்று செலவு செய்யலாம்';

  @override
  String get perDay => 'தினமும்';

  @override
  String get leftToday => 'இன்று மீதம்';

  @override
  String get spentToday => 'இன்று செலவு';

  @override
  String daysLeft(int n) {
    return '$n நாட்கள் உள்ளன';
  }

  @override
  String overToday(String amount) {
    return 'இன்றைய தொகையை விட $amount அதிகம்';
  }

  @override
  String get nothingLeft => 'இந்த மாதம் தாராளமாக செலவு செய்ய எதுவும் மீதமில்லை';

  @override
  String get stsIncome => 'வருமானம்';

  @override
  String get stsCommitted => 'பில்கள் & இஎம்ஐ';

  @override
  String get stsGoals => 'இலக்குகள்';

  @override
  String get stsSpent => 'செலவு';

  @override
  String get stsFormula => 'வருமானத்திலிருந்து பில்களும் இலக்குகளும் கழித்து, இதுவரை செலவானதைக் கழித்து, மீதமுள்ள நாட்களுக்குப் பகிர்ந்தது.';

  @override
  String get wPockets => 'பாக்கெட்டுகள்';

  @override
  String get wGoals => 'இலக்குகள்';

  @override
  String get wSpend => 'பணம் எங்கே போகிறது';

  @override
  String get wCashFlow => 'வரவு செலவு';

  @override
  String get wTransactions => 'சமீபத்தியவை';

  @override
  String get wBills => 'பில்கள் & இஎம்ஐ';

  @override
  String get wNetWorth => 'நிகர சொத்து';

  @override
  String get wInvestments => 'முதலீடுகள்';

  @override
  String get wInsight => 'போகோ கவனித்தது';

  @override
  String get wPulse => 'பல்ஸ்';

  @override
  String get wGroup => 'குழு';

  @override
  String get whyLayout => 'ஏன் இந்த அமைப்பு?';

  @override
  String get whyLayoutTitle => 'உங்கள் முகப்பு ஏன் இப்படி உள்ளது';

  @override
  String get editHome => 'முகப்பைத் திருத்து';

  @override
  String get editHomeHint => 'இழுத்து வரிசையை மாற்றுங்கள். செலவு வரம்பு எப்போதும் மேலே இருக்கும்.';

  @override
  String get resetHome => 'போகோவின் அமைப்புக்குத் திரும்பு';

  @override
  String get askPokoChange => 'போகோவிடம் மாற்றச் சொல்லுங்கள்';

  @override
  String get homeSaved => 'முகப்பு சேமிக்கப்பட்டது';

  @override
  String ofLimit(String limit) {
    return '$limit-இல்';
  }

  @override
  String leftLabel(String amount) {
    return '$amount மீதம்';
  }

  @override
  String overLabel(String amount) {
    return '$amount அதிகம்';
  }

  @override
  String get statusOver => 'தாண்டியது';

  @override
  String get statusWatch => 'கவனம்';

  @override
  String get statusOk => 'சரியாக';

  @override
  String get statusBehind => 'பின்தங்கி';

  @override
  String get statusReached => 'எட்டியது';

  @override
  String get statusPaused => 'நிறுத்தம்';

  @override
  String get thisMonth => 'இந்த மாதம்';

  @override
  String get income => 'வரவு';

  @override
  String get spend => 'செலவு';

  @override
  String dueIn(int n) {
    return '$n நாட்களில்';
  }

  @override
  String get dueToday => 'இன்று';

  @override
  String get dueTomorrow => 'நாளை';

  @override
  String get overdue => 'நிலுவை';

  @override
  String get autopay => 'தானியங்கி';

  @override
  String get assets => 'உங்களிடம் உள்ளது';

  @override
  String get liabilities => 'நீங்கள் தர வேண்டியது';

  @override
  String get weekChange => 'இந்த வாரம்';

  @override
  String get viewOnly => 'பார்க்க மட்டும். பாக்கெட் ஒருபோதும் வாங்கவோ விற்கவோ சொல்லாது.';

  @override
  String get noInsights => 'சொல்ல புதிதாக எதுவும் இல்லை';

  @override
  String get noInsightsBody => 'போகோ கவனித்துக்கொண்டிருக்கிறது. வடிவங்கள் இங்கே தெரியும்.';

  @override
  String get forYou => 'உங்களுக்கு';

  @override
  String youOwe(String amount) {
    return 'நீங்கள் $amount தர வேண்டும்';
  }

  @override
  String youAreOwed(String amount) {
    return 'உங்களுக்கு $amount வர வேண்டும்';
  }

  @override
  String get allSettled => 'கணக்கு சரி';

  @override
  String get dismiss => 'நீக்கு';

  @override
  String get moneyTitle => 'பணம்';

  @override
  String get segTransactions => 'பரிவர்த்தனைகள்';

  @override
  String get segAccounts => 'கணக்குகள்';

  @override
  String get segBills => 'பில்கள் & இஎம்ஐ';

  @override
  String get segInvestments => 'முதலீடுகள்';

  @override
  String get searchHint => 'கடை அல்லது குறிப்பைத் தேடுங்கள்';

  @override
  String get filterAll => 'அனைத்தும்';

  @override
  String get filterOut => 'செலவு';

  @override
  String get filterIn => 'வரவு';

  @override
  String get addCash => 'ரொக்கப் பதிவு சேர்';

  @override
  String get amountRupees => 'தொகை (₹)';

  @override
  String get whatWasIt => 'இது என்ன?';

  @override
  String get category => 'வகை';

  @override
  String get changeCategory => 'வகையை மாற்று';

  @override
  String get splitWithGroup => 'குழுவுடன் பகிர்';

  @override
  String get noTransactions => 'பரிவர்த்தனை எதுவும் இல்லை';

  @override
  String get owedOnCard => 'நிலுவை';

  @override
  String get limitLabel => 'வரம்பு';

  @override
  String emisLeft(int n) {
    return '$n இஎம்ஐ மீதம்';
  }

  @override
  String get outstanding => 'மீதமுள்ள கடன்';

  @override
  String get invested => 'முதலீடு செய்தது';

  @override
  String get approx => 'தோராயம்';

  @override
  String get noBills => 'விரைவில் கட்ட எதுவும் இல்லை';

  @override
  String get noInvestments => 'முதலீடுகள் இணைக்கப்படவில்லை';

  @override
  String get mascotTalk => 'பேசு';

  @override
  String get mascotNoticed => 'கவனித்தவை';

  @override
  String get mascotPulse => 'பல்ஸ்';

  @override
  String get typeHint => 'உங்கள் பணத்தைப் பற்றிக் கேளுங்கள்';

  @override
  String get micStart => 'பேச தட்டுங்கள்';

  @override
  String get micStop => 'நிறுத்த தட்டுங்கள்';

  @override
  String get connecting => 'இணைகிறது';

  @override
  String get voiceOffNote => 'லைவ் கீ அமைத்ததும் குரல் இயங்கும். இப்போது தட்டச்சு செய்து பேசுங்கள்.';

  @override
  String get mascotOffline => 'போகோவுக்கு இணையம் தேவை. உங்கள் எண்கள் இங்கேயே உள்ளன.';

  @override
  String get confirmCardNote => 'உறுதிசெய் என்பதைத் தட்டும் வரை எதுவும் நடக்காது.';

  @override
  String get proposalDone => 'முடிந்தது. உங்கள் எண்கள் புதுப்பிக்கப்பட்டன.';

  @override
  String get proposalFailed => 'இதைச் செய்ய முடியவில்லை. எதுவும் மாறவில்லை.';

  @override
  String get promptToday => 'இன்று எவ்வளவு செலவு செய்யலாம்?';

  @override
  String get promptSpend => 'என் பணம் எங்கே போகுது?';

  @override
  String get promptNotice => 'நீங்கள் என்ன கவனித்தீர்கள்?';

  @override
  String get promptFund => 'இந்த ஃபண்ட் வாங்கலாமா?';

  @override
  String get promptBills => 'என் பில்களை முதலில் வை';

  @override
  String get pulseEmpty => 'இன்றைய பல்ஸ் இன்னும் வரவில்லை';

  @override
  String get pulseEmptyBody => 'சந்தை, உலகச் செய்திகள் ஆதாரத்துடன் இங்கே தெரியும்.';

  @override
  String get planTitle => 'திட்டம்';

  @override
  String get suggested => 'பரிந்துரைத்த மாற்றங்கள்';

  @override
  String get newPocket => 'புதிய பாக்கெட்';

  @override
  String get newGoal => 'புதிய இலக்கு';

  @override
  String get nameLabel => 'பெயர்';

  @override
  String get monthlyLimit => 'மாத வரம்பு (₹)';

  @override
  String get targetAmount => 'இலக்குத் தொகை (₹)';

  @override
  String get pausePocket => 'நிறுத்து';

  @override
  String get resumePocket => 'தொடர்';

  @override
  String needPerMonth(String amount) {
    return 'மாதம் $amount தேவை';
  }

  @override
  String byDate(String date) {
    return '$date-க்குள்';
  }

  @override
  String get noPockets => 'இன்னும் பாக்கெட் இல்லை';

  @override
  String get noGoals => 'இன்னும் இலக்கு இல்லை';

  @override
  String get collabTitle => 'சேர்ந்து';

  @override
  String get newGroup => 'புதிய குழு';

  @override
  String get joinGroup => 'குறியீட்டால் சேர்';

  @override
  String get inviteCode => 'அழைப்புக் குறியீடு';

  @override
  String get groupName => 'குழுவின் பெயர்';

  @override
  String get typeFamily => 'குடும்பம்';

  @override
  String get typeTrip => 'பயணம்';

  @override
  String get typeFlatmates => 'அறைத் தோழர்கள்';

  @override
  String get typeCustom => 'பிற';

  @override
  String get members => 'உறுப்பினர்கள்';

  @override
  String get expenses => 'செலவுகள்';

  @override
  String get settleUp => 'கணக்கு தீர்';

  @override
  String get addExpense => 'செலவு சேர்';

  @override
  String get paidBy => 'கொடுத்தவர்';

  @override
  String get splitEqual => 'சமமாகப் பகிர்';

  @override
  String get addGuest => 'விருந்தினரைச் சேர்';

  @override
  String get guestUpi => 'யுபிஐ ஐடி (விருப்பம்)';

  @override
  String get payByUpi => 'யுபிஐ மூலம் செலுத்து';

  @override
  String get openUpiApp => 'யுபிஐ செயலியைத் திற';

  @override
  String get copyUpiId => 'யுபிஐ ஐடியை நகலெடு';

  @override
  String get copied => 'நகலெடுக்கப்பட்டது';

  @override
  String get markPaid => 'நான் செலுத்திவிட்டேன்';

  @override
  String get confirmReceived => 'பெற்றதை உறுதிசெய்';

  @override
  String pays(String from, String to) {
    return '$from தருவார் $to-க்கு';
  }

  @override
  String get pocketNeverHolds => 'பாக்கெட் ஒருபோதும் பணத்தை வைத்திருக்காது. உங்கள் யுபிஐ செயலியில்தான் செலுத்துகிறீர்கள்.';

  @override
  String get demoUpiNote => 'டெமோ யுபிஐ ஐடிகள் (@pocketdemo) உண்மையானவை அல்ல; பணம் எதுவும் போகாது.';

  @override
  String get sharedBudget => 'பொது பட்ஜெட்';

  @override
  String get pot => 'பாட்';

  @override
  String get addToPot => 'பாட்டில் சேர்';

  @override
  String get privacyGroup => 'இந்தக் குழு என்ன பார்க்கும்';

  @override
  String get privacyGroupNote => 'நீங்கள் இயக்கும் வரை உங்களுடையது எதுவும் பகிரப்படாது.';

  @override
  String get shareNothing => 'எதுவும் பகிரப்படவில்லை';

  @override
  String get noGroups => 'இன்னும் குழு இல்லை';

  @override
  String get noGroupsBody => 'பயணம், வீடு அல்லது குடும்பத்திற்காக ஒன்றைத் தொடங்குங்கள்.';

  @override
  String get you => 'நீங்கள்';

  @override
  String get guest => 'விருந்தினர்';

  @override
  String get statusPending => 'நிலுவையில்';

  @override
  String get statusLinkOpened => 'இணைப்பு திறந்தது';

  @override
  String get statusMarkedPaid => 'செலுத்தியதாகக் குறித்தது';

  @override
  String get statusConfirmed => 'உறுதியானது';

  @override
  String yourShare(String amount) {
    return 'உங்கள் பங்கு $amount';
  }

  @override
  String membersCount(int n) {
    return '$n உறுப்பினர்கள்';
  }

  @override
  String get profileTitle => 'சுயவிவரம்';

  @override
  String get language => 'மொழி';

  @override
  String get mascotVoice => 'போகோவின் குரல்';

  @override
  String get nudgesTitle => 'நினைவூட்டல்கள்';

  @override
  String get nudgesPerDay => 'ஒரு நாளைக்கு எத்தனை';

  @override
  String get quietHours => 'அமைதி நேரம்';

  @override
  String get privacy => 'தனியுரிமை';

  @override
  String get exportData => 'என் தரவை ஏற்றுமதி செய்';

  @override
  String get deleteData => 'என் தரவை அழி';

  @override
  String get deleteConfirm => 'இது பாக்கெட்டில் உங்களைப் பற்றிய அனைத்தையும் நீக்கும். மீட்க முடியாது.';

  @override
  String get disclaimerTitle => 'தகவல், ஆலோசனை அல்ல';

  @override
  String get disclaimerBody => 'பாக்கெட் உங்கள் சொந்த எண்களையும் பொதுவான விளக்கங்களையும் காட்டுகிறது. எந்த முதலீட்டையும் வாங்க, விற்க, மாற்ற அது ஒருபோதும் சொல்லாது. இந்தப் பதிப்பில் உள்ள அனைத்துத் தரவும் செயற்கையானது.';

  @override
  String get switchPersona => 'டெமோ சுயவிவரத்தை மாற்று';

  @override
  String get demoTools => 'டெமோ கருவிகள்';

  @override
  String get injectSwiggy => 'இப்போது ஒரு ஸ்விக்கி ஆர்டர் சேர்';

  @override
  String get linkedAccounts => 'இணைந்த கணக்குகள்';

  @override
  String get startOver => 'புதிதாகத் தொடங்கு';

  @override
  String exported(int n) {
    return 'ஏற்றுமதி தயார்: $n பரிவர்த்தனைகள்';
  }

  @override
  String get muteVoice => 'குரலை அணை';

  @override
  String get smsTitle => 'ஒரு வங்கி SMS இப்போது வந்தது';

  @override
  String get smsReadAs => 'பாக்கெட் இதை இப்படிப் படித்தது';

  @override
  String get smsSynthetic => 'இந்தச் செய்தி டெமோவுக்காக உருவாக்கப்பட்டது. பாக்கெட் உங்கள் போனில் உள்ள SMS-ஐப் படிப்பதில்லை.';

  @override
  String get smsSeeHome => 'முகப்பில் பார்க்க';
}
