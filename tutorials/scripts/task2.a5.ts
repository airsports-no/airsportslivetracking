import { defineTutorial } from "../src/runner/tutorial";

// A starting point: copy this file, record the clicks with windows/codegen.ps1 (see GUIDE.md) and paste them into run().
export default defineTutorial({
  title: "Task 2.A5 Navigation with unknown legs",
  subtitle: "This tutorial shows how to create a navigation task with unknown legs.",
  // Shown above the title and in the header during the video
  series: "Route creation",
  // On the end screen, when there is a next tutorial to watch
  next: "",
  // What the tutorial creates, deleted before every recording so the replay does not find two of them
  cleanUp: {
    routes: ["Task 2.A5 Unknown legs"],
    navigationTasks: ["Task 2.A5 Unknown legs"],
    // Only where the task is looked for: the contest itself is kept
    contest: "Tutorial contest",
  },
  startUrl: "/routeeditor/create",
  async run() {
// Recorded 2026-10-23T17:43:07.964Z from http://localhost:8002/routeeditor/create

await map.view(60.8, 11.1, 11);
await say("This tutorial shows how to build a route for task 2.A5, navigation with unknown legs, and what the contestants get to see.");

// ── Phase: Task wizard ──
await chapter("Task wizard");
await say("Open the task wizard in the route editor and choose 2.A5, navigation with unknown legs. The wizard then takes you through the route step by step.", { wait: false });
await page.getByRole('button', { name: 'Task Wizard' }).click();
await page.getByRole('button', { name: '2.A5 Navigation with unknown' }).click();

// ── Phase: Backbone route ──
await chapter("Backbone route");
await say("First, build the backbone: the route the contestants actually fly, from the starting point to the finish point. While placing its waypoints, plan which of them will be unknown waypoints, and where their dummy legs should go.", { wait: false });
await page.getByRole('button', { name: 'Start' }).click();
await map.wheel([[793,572,-100,0],[816,527,-100,267],[819,516,-100,142],[843,444,-100,365]]);
await map.view(60.7901284, 11.1043453, 14);
await map.drag([[936,324,0],[936,324,29],[936,325,121],[936,326,33],[936,327,25],[936,328,17],[936,329,25],[936,331,20],[935,333,30],[934,335,17],[933,338,33],[931,343,33],[930,345,17],[929,347,17],[928,349,17],[926,352,17],[924,356,17],[922,359,17],[919,362,17],[915,368,17],[912,372,25],[910,375,17],[907,378,17],[905,381,17],[902,385,17],[899,389,17],[897,392,20],[895,396,22],[891,401,17],[888,403,16],[885,407,17],[883,409,17],[880,412,17],[877,416,17],[874,420,17],[871,423,17],[868,426,17],[863,431,25],[858,435,25],[854,440,17],[849,446,17],[844,450,17],[841,454,17],[839,456,25],[834,461,17],[829,465,33],[826,467,20],[823,468,23],[820,469,24],[817,472,17],[813,474,17],[806,477,17],[801,481,17],[797,483,17],[793,484,17],[790,486,17],[786,488,17],[784,489,17],[782,490,20],[775,492,30],[773,492,25],[770,493,16],[768,494,17],[766,494,17],[764,495,17],[762,495,17],[760,496,25],[758,497,17],[755,499,17],[751,500,25],[749,500,25],[746,501,62],[741,502,21],[738,503,17],[734,504,17],[730,504,17],[728,505,17],[724,506,23],[722,506,24],[719,507,28],[719,507,1517]], {"at":[60.7977927,11.1160183],"zoom":14});
await map.view(60.7977927, 11.1229706, 14);
await map.click(60.7983789, 11.1088943);
await map.wheel([[655,611,100,0],[661,631,100,125],[667,653,100,100]]);
await map.drag([[730,886,0],[730,886,33],[731,886,17],[731,884,17],[731,880,17],[729,873,17],[727,864,17],[722,851,17],[720,839,17],[717,832,17],[711,815,17],[708,806,17],[698,776,17],[694,764,17],[690,752,17],[686,742,17],[679,723,20],[671,706,22],[666,691,17],[660,678,16],[652,657,16],[647,642,17],[642,624,17],[636,602,17],[629,573,17],[625,554,17],[621,535,17],[614,498,18],[607,465,24],[603,451,17],[601,440,17],[598,432,17],[596,427,17],[595,424,16],[595,424,180]], {"at":[60.7703939,11.1234856],"zoom":13});
await map.view(60.7634357, 11.1586761, 13);
await map.click(60.7524505, 11.1590195);
await map.click(60.7785238, 11.1873436);
await map.drag([[773,294,0],[773,295,67],[773,299,18],[773,306,19],[777,321,31],[781,339,18],[784,350,16],[787,359,17],[789,368,17],[792,381,17],[794,396,17],[796,407,17],[798,417,17],[800,425,16],[801,436,17],[802,442,17],[804,454,17],[806,467,17],[808,485,17],[808,497,17],[810,511,17],[811,524,17],[813,545,17],[815,560,17],[817,573,17],[818,580,17],[822,608,17],[825,621,22],[830,642,23],[833,655,30],[836,665,17],[840,675,16],[844,684,19],[849,700,23],[852,709,17],[854,718,21],[856,721,21],[857,728,17],[859,733,17],[859,736,17],[860,739,17],[860,741,17],[861,745,17],[862,750,17],[863,753,17],[863,756,17],[865,759,17],[865,761,17],[866,764,20],[868,768,23],[870,773,24],[871,775,16],[871,777,20],[871,778,22],[871,780,45],[871,780,766]], {"at":[60.7812892,11.1540413],"zoom":13});
await map.view(60.8041572, 11.1418533, 13);
await map.click(60.8217369, 11.1509514);
await map.click(60.8223227, 11.2081146);
await map.click(60.7960338, 11.270771);
await say("Press Done when the backbone reaches the finish point.", { wait: false });
await page.getByRole('button', { name: 'Done' }).click();

// ── Phase: Unknown leg 1 ──
await chapter("Unknown leg 1");
await say("Next, choose the first unknown waypoint. Press Add under unknown-leg triggers, then click the backbone waypoint the contestants must find. In the flight order they only get a photo of it.", { wait: false });
await page.getByRole('button', { name: 'Task Wizard' }).click();
// The Add of the wizard's "Unknown-leg triggers" step, by its title (not the first Add on the page)
await page.getByText(/^\d+\. Unknown-leg triggers$/).locator("xpath=ancestor::div[.//button][1]").getByRole('button', { name: 'Add' }).click();
await map.drag([[579,781,0],[580,781,33],[580,780,26],[580,778,24],[580,774,17],[580,772,17],[580,768,18],[575,747,24],[572,739,17],[568,724,17],[564,713,17],[557,690,17],[553,679,33],[535,632,17],[526,612,16],[518,597,17],[510,584,17],[503,571,17],[494,557,17],[486,544,17],[474,526,17],[466,515,17],[460,504,17],[453,495,17],[449,487,17],[445,481,17],[442,477,17],[439,472,18],[438,472,106]], {"at":[60.7812054,11.1038956],"zoom":13});
await map.view(60.7782724, 11.1660604, 13);
await map.click(60.7522828, 11.159177);
await say("The wizard goes straight on to the dummy leg: click where it should lead. It is drawn on the contestants' map, and hides where the unknown waypoint really is.", { wait: false });
await map.click(60.7387766, 11.1767034);

// ── Phase: Unknown leg 2 ──
await chapter("Unknown leg 2");
await say("Do the same for the second unknown leg, then press Done.", { wait: false });
await page.getByRole('button', { name: 'Task Wizard' }).click();
// The Add of the wizard's "Unknown-leg triggers" step, by its title (not the first Add on the page)
await page.getByText(/^\d+\. Unknown-leg triggers$/).locator("xpath=ancestor::div[.//button][1]").getByRole('button', { name: 'Add' }).click();
await map.drag([[660,252,0],[661,252,51],[661,253,22],[662,255,18],[662,262,20],[662,266,17],[662,272,17],[662,278,17],[662,285,17],[660,302,17],[659,309,17],[658,318,17],[656,331,17],[655,340,17],[655,351,17],[653,362,17],[652,369,17],[651,382,17],[648,402,17],[647,412,17],[646,422,17],[645,442,17],[644,466,25],[644,481,17],[644,496,17],[644,509,17],[643,520,17],[643,534,17],[643,546,17],[643,551,17],[642,561,17],[642,567,16],[642,573,17],[642,578,17],[642,587,17],[640,602,17],[639,611,17],[639,620,17],[638,625,17],[638,633,17],[638,647,17],[638,653,17],[638,663,17],[638,669,17],[638,681,17],[637,691,17],[637,697,17],[637,703,17],[637,708,17],[637,720,17],[636,723,17],[636,725,17],[636,726,41]], {"at":[60.7996352,11.142012],"zoom":13});
await map.view(60.8179706, 11.1701807, 13);
await map.click(60.8215695, 11.1511109);
await map.click(60.8325311, 11.1425432);
await page.getByRole('button', { name: 'Done' }).click();

// ── Phase: Secrets ──
await chapter("Secrets");
await say("To make the route harder, add hidden gates along the backbone, even on the leg after an unknown waypoint. They are not on the contestants' map, but passing them is checked.", { wait: false });
// The Add of the wizard's "Hidden gates" step, by its title (not the third Add on the page)
await page.getByText(/^\d+\. Hidden gates \(optional\)$/).locator("xpath=ancestor::div[.//button][1]").getByRole('button', { name: 'Add' }).click();
await map.wheel([[936,467,-100,0],[936,467,-100,186],[936,467,-100,142],[936,467,-100,124],[936,467,-100,150]]);
await map.view(60.8209, 11.1906056, 16);
await map.click(60.8221658, 11.1921076);
await map.wheel([[871,392,100,0],[871,393,100,108],[880,409,100,66],[889,427,100,50],[892,432,100,329],[892,432,100,45],[892,432,100,43],[892,432,100,50]]);
await map.wheel([[881,494,100,0]]);
await map.view(60.8175521, 11.1780771, 13);
await map.drag([[842,758,0],[842,757,59],[842,756,21],[842,749,19],[843,742,23],[843,736,17],[843,723,17],[844,709,17],[844,700,17],[845,688,17],[846,680,17],[847,656,17],[847,647,17],[848,630,17],[848,620,17],[849,599,17],[849,581,17],[849,566,17],[849,540,17],[849,524,17],[849,477,17],[848,456,16],[846,435,17],[844,397,17],[840,359,17],[837,311,17],[834,292,17],[831,259,18],[825,221,24],[822,196,17],[820,186,17],[818,177,17],[817,168,25],[816,162,204]], {"at":[60.7965363,11.1852869],"zoom":13});
await map.view(60.7676276, 11.1825403, 13);
await map.wheel([[760,500,-100,0],[760,500,-100,113],[760,500,-100,108],[760,500,-100,118]]);
await map.view(60.7680677, 11.177388, 15);
await map.click(60.7678372, 11.1756714);
await map.wheel([[958,531,100,0],[958,531,100,98],[958,531,100,33],[958,531,100,125],[958,531,100,92]]);
await map.view(60.7695556, 11.1569628, 13);
await map.drag([[819,347,0],[819,349,44],[816,358,23],[813,364,17],[810,371,17],[805,381,17],[803,389,17],[799,401,17],[798,407,17],[796,418,17],[794,426,17],[791,441,17],[790,446,17],[788,451,17],[785,465,17],[782,478,17],[780,485,17],[777,496,17],[777,502,17],[776,508,17],[773,519,17],[773,523,17],[771,526,20],[770,529,278]], {"at":[60.782965,11.1602243],"zoom":13});
await map.view(60.7848084, 11.1653742, 13);
await map.click(60.8086786, 11.1619409);
await page.getByRole('button', { name: 'Done' }).click();

// ── Phase: Curve ──
await chapter("Curve");
await say("Legs can also be curved. Click the waypoint at the end of the leg, press Make Curved, and drag the curve into shape.", { wait: false });
await map.click(60.7520312, 11.1585077);
await page.getByRole('button', { name: 'Make Curved' }).click();
await map.drag([[617,622,0],[614,622,29],[613,622,23],[611,622,25],[609,622,17],[606,623,17],[599,626,17],[592,630,17],[580,636,35],[540,657,24],[531,663,16],[520,670,17],[509,678,16],[501,685,17],[484,698,17],[476,704,17],[460,716,17],[448,725,17],[421,746,16],[410,754,17],[400,761,17],[397,764,17],[390,768,17],[383,772,17],[380,774,17],[379,775,778]], {"at":[60.7751715,11.1339403],"zoom":13});
await map.drag([[1013,916,0],[1013,915,59],[1013,914,20],[1013,911,18],[1012,900,24],[1008,886,17],[1003,870,17],[998,855,17],[988,824,17],[983,803,17],[979,786,17],[972,760,19],[960,714,23],[956,697,17],[956,687,17],[954,667,17],[952,643,18],[952,616,24],[952,603,17],[952,576,17],[952,554,18],[954,541,24],[961,510,17],[962,504,17],[962,502,17],[962,502,122]], {"at":[60.7505214,11.2019261],"zoom":13});
await map.wheel([[962,502,-100,0],[962,502,-100,120]]);
await map.view(60.7503117, 11.1880324, 14);
await map.drag([[670,785,0],[670,784,96],[672,782,22],[675,778,17],[679,775,17],[685,770,17],[691,763,17],[705,750,17],[715,740,17],[724,729,17],[730,722,17],[737,715,16],[754,699,17],[761,693,17],[770,686,17],[785,673,17],[794,663,17],[799,657,16],[804,651,17],[809,642,17],[814,631,17],[824,610,17],[830,596,17],[834,585,17],[837,576,18],[839,563,24],[839,559,17],[840,555,17],[840,553,18],[841,551,30],[841,548,19],[841,545,19],[841,541,22],[841,539,18],[842,534,17],[843,532,17],[845,527,17],[847,523,17],[851,518,17],[854,514,17],[858,510,17],[865,503,17],[866,501,22],[867,500,19],[867,498,17],[868,495,17],[870,492,25],[870,488,19],[871,485,23],[871,482,24],[871,479,33],[871,475,17],[871,473,17],[871,471,17],[871,469,19],[873,465,23],[875,461,25],[879,455,17],[880,453,17],[882,450,24],[882,449,18],[883,447,17],[883,444,33],[884,443,25],[884,441,17],[885,440,17],[885,437,17],[885,434,16],[886,432,17],[886,430,17],[886,428,17],[886,426,16],[887,422,22],[887,420,121],[887,415,24],[887,412,17],[887,408,17],[887,405,17],[887,399,17],[887,397,17],[887,394,229],[887,392,29],[888,389,17],[888,386,17],[888,384,17],[888,381,19],[888,380,127],[889,377,23],[890,374,23],[890,371,22],[891,370,20],[891,370,228]], {"at":[60.7386508,11.176865],"zoom":14});
await map.click(60.7558052, 11.1956641);
await page.getByRole('button', { name: 'Make Curved' }).click();
await say("Do the same for any other leg that should be curved.", { wait: false });
await map.drag([[677,413,0],[677,414,169],[677,417,17],[677,419,17],[678,424,23],[679,426,23],[680,428,29],[681,429,17],[681,432,20],[682,435,23],[684,437,23],[684,440,17],[685,441,17],[686,444,17],[687,447,17],[689,449,17],[689,451,17],[690,452,17],[690,454,17],[692,456,17],[692,458,17],[693,460,20],[694,461,22],[694,463,17],[696,465,17],[697,467,33],[698,469,17],[698,470,25],[699,471,20],[700,472,23],[700,473,293],[701,475,21],[701,477,18],[702,478,17],[702,480,17],[703,481,17],[703,482,25],[703,484,20],[704,486,30],[704,488,25],[705,491,22],[706,495,20],[706,497,25],[706,499,20],[706,499,286]], {"at":[60.7542537,11.1774659],"zoom":14});
await map.drag([[706,499,0],[707,499,232],[708,500,22],[709,502,33],[710,503,19],[710,504,22],[710,504,249]], {"at":[60.7506472,11.1799552],"zoom":14});
await map.click(60.7502279, 11.1804703);
await map.click(60.7437687, 11.18708);
await map.wheel([[780,663,100,0],[795,684,100,143]]);
await map.view(60.7568115, 11.1897511, 13);
await map.drag([[1104,410,0],[1104,412,74],[1104,417,30],[1104,425,23],[1105,432,17],[1105,441,17],[1105,449,17],[1106,457,17],[1106,472,16],[1106,485,17],[1106,497,17],[1106,510,17],[1106,527,17],[1105,539,17],[1103,555,16],[1102,566,17],[1100,584,17],[1097,613,17],[1095,625,17],[1093,637,17],[1091,655,17],[1089,670,17],[1089,678,17],[1089,686,17],[1089,693,17],[1089,697,17],[1089,706,16],[1089,709,17],[1090,712,17],[1090,714,17],[1090,718,17],[1091,721,17],[1091,725,21],[1091,730,21],[1091,735,16],[1091,740,23],[1090,740,316]], {"at":[60.7649449,11.2419362],"zoom":13});
await map.drag([[1058,627,0],[1058,628,105],[1058,635,23],[1057,640,17],[1057,647,17],[1057,654,17],[1057,662,17],[1057,667,17],[1057,673,17],[1057,678,17],[1057,681,17],[1057,687,17],[1057,689,17],[1056,690,25],[1056,692,78],[1056,695,23],[1055,698,17],[1054,700,17],[1054,702,57]], {"at":[60.7744172,11.236443],"zoom":13});
await map.view(60.7907567, 11.192841, 13);

// ── Phase: Save ──
await chapter("Save");
await say("Finally, give the route a name and save it.", { wait: false });
await page.getByRole('textbox', { name: 'Route Name' }).click();
await page.getByRole('textbox', { name: 'Route Name' }).fill("Task 2.A5 Unknown legs");
await page.getByRole('button', { name: 'Save Route' }).click();
// A dialog asks "Route has validation errors. Save anyway?": the recording accepts it
await map.view(60.7925158, 11.1898327, 13);

// ── Hidden from the video ──
await startHidden();
await page.getByRole('link', { name: 'Back' }).click();
// The route by its full name, not by the place of its card in the list (div:nth-child(28) when recorded)
await page.getByRole('searchbox', { name: 'Search routes by name' }).fill("Task 2.A5 Unknown legs");
await page.getByRole('button', { name: 'Create task' }).first().click();
await page.locator('.my-react-select__input-container').click();
await page.getByRole('option', { name: '2.A5 Navigation with unknown legs', exact: true }).click();
await page.locator('.my-react-select__input-container').click();
await page.getByRole('option', { name: 'Tutorial contest' }).click();
await page.getByRole('textbox', { name: 'Name' }).click();
await page.getByRole('textbox', { name: 'Name' }).fill("Task 2.A5 Unknown legs");
await page.getByRole('checkbox', { name: 'Allow self-management Lets' }).click();
await page.getByRole('checkbox', { name: 'Allow observation' }).click();
// Today, 09:00 to 18:00 (the recorded date would soon be in the past)
const today = new Date().toLocaleDateString("sv-SE");
await page.getByRole('textbox', { name: 'Start time' }).fill(`${today}T09:00`);
await page.getByRole('textbox', { name: 'Finish time' }).fill(`${today}T18:00`);
await page.getByText('Add a navigation taskTask').click();
await page.getByRole('button', { name: 'Create navigation task' }).click();
await page.getByRole('button', { name: 'Continue' }).click();
await page.getByRole('link', { name: 'Live Map' }).click();
await endHidden();
// ── Shown again ──

// ── Phase: Live map ──
await chapter("Live map");
await say("On the live map you see the whole route the contestants will fly, with the hidden gates and the dummy legs.");

// ── Phase: Live map with hidden secrets ──
await chapter("Live map with hidden secrets");
// Said while the secret gates are turned off
await say("Turn off the secret gates, and you see the map the contestants get:", { wait: false });

await page.getByRole('button', { name: 'Settings' }).click();
await page.getByRole('checkbox', { name: 'Show Secret Gates' }).click();
await say("the dummy legs are drawn, but the unknown legs are not.", { wait: false });

// ── Phase: Flight order ──
await chapter("Flight order");
// The whole page first, then zoomed in on the route: the map (without the page's margins) fills the width
await showPdf("pdfs/flight_orders 2.A5.pdf", { pages: [4], width: "page" });
await say("The flight order holds the navigation map the contestants navigate by during the flight.", { wait: false });
await pause(1200);
await zoomPdf(4, { y: 0.31, height: 0.36, x: 0.048, width: 0.904 });
await say("It shows the backbone and the dummy legs, but not the unknown legs.");
// Small enough for all four photos to fit in the window
await showPdf("pdfs/flight_orders 2.A5.pdf", { pages: [5], width: 0.62 });
await say("Next come the photos of the unknown waypoints, in random order and mixed in with decoy photos, so the contestants cannot tell which are real. The number on each photo is the course to fly from that point.", { wait: false });
await highlight(await pdfRegion(5, { x: 0.04, y: 0.05, width: 0.92, height: 0.53 }), { label: "Unknown leg and decoy photos", durationMs: 9000 });
await say("The route is ready. In photo management you can replace these satellite pictures with real aerial photos of the unknown waypoints.");
  },
});
