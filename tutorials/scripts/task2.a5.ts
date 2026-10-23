import { defineTutorial } from "../src/runner/tutorial";

// A starting point: copy this file, record the clicks with windows/codegen.ps1 (see GUIDE.md) and paste them into run().
export default defineTutorial({
  title: "Task 2.A5 Navigation with unknown legs",
  subtitle: "This tutorial shows how to create a navigation task with unknown legs.",
  // Shown above the title and in the header during the video
  series: "Route creation",
  // On the end screen, when there is a next tutorial to watch
  next: "Creating a contest",
  // What the tutorial creates, deleted before every recording so the replay does not find two of them
  cleanUp: {
    routes: ["Task 2.A5 Unknown legs"],
    navigationTasks: ["Task 2.A5 Unknown legs"],
    // Only where the task is looked for: the contest itself is kept
    contest: "Tutorial contest",
  },
  startUrl: "/routeeditor/create",
  async run() {
    camera("wide");
// Recorded 2026-10-23T10:14:49.317Z from http://localhost:8002/routeeditor/create
// Paste these lines into run() of the tutorial script.

await map.view(60.8, 11.1, 11);
await say("This tutorial shows how to build a route for task 2.A5, navigation with unknown legs, and what the contestants get to see.");

// ── Phase: Task wizard ──
await chapter("Task wizard");
await say("After opening the route editor, open the task wizard and choose 2.A5, navigation with unknown legs.", { wait: false });
await page.getByRole('button', { name: 'Task Wizard' }).click();
await page.getByRole('button', { name: '2.A5 Navigation with unknown' }).click();

// ── Phase: Route path ──
await chapter("Route path");
await say("First, build the route the contestants will actually fly. We call this the backbone. While placing its waypoints, plan which ones will be unknown waypoints, and where their dummy legs should go.", { wait: false });
await map.drag([[924,600,0],[923,599,112],[922,597,30],[921,596,21],[921,595,24],[916,593,23],[890,582,22],[882,579,23],[874,575,22],[862,569,23],[856,566,22],[850,564,41],[837,557,17],[815,546,17],[803,540,17],[796,536,22],[776,521,31],[760,511,23],[755,506,22],[739,496,28],[734,491,25],[718,480,17],[712,474,17],[705,469,33],[700,466,25],[684,456,17],[664,444,20],[643,436,22],[633,432,23],[610,426,19],[591,422,17],[587,421,17],[581,420,17],[577,420,16],[564,420,17],[560,420,17],[559,420,50],[559,422,17],[559,422,235]]);
await map.view(60.7403708, 11.3509369, 11);
await map.wheel([[458,361,-100,0],[458,361,-100,89],[458,361,-100,108],[458,361,-100,118],[458,361,-100,124],[458,361,-100,107]]);
await map.view(60.7770991, 11.1748123, 13);
await page.getByRole('button', { name: 'Start' }).click();
await map.click(60.8001376, 11.1176491);
await map.click(60.7526183, 11.1588478);
await map.click(60.7853111, 11.2055397);

// ── Hidden from the video ──
await startHidden();
await map.wheel([[1007,512,100,0]]);
await map.drag([[943,260,0],[945,261,22],[947,263,21],[949,270,17],[950,282,17],[950,296,21],[947,328,23],[946,346,23],[945,362,17],[943,378,17],[943,392,17],[943,398,17],[943,407,16],[943,409,17],[943,412,19],[943,415,30],[943,417,23],[942,417,38]]);
await map.wheel([[896,400,-100,0],[889,400,-100,235],[883,400,-100,231]]);
await map.view(60.8171755, 11.1633968, 14);
await endHidden();
// ── Shown again ──
await map.click(60.8217787, 11.1664009);

// ── Hidden from the video ──
await startHidden();
await map.wheel([[1227,474,100,0],[1228,477,100,81],[1229,478,100,55]]);
await map.drag([[1271,287,0],[1271,288,82],[1268,301,30],[1252,330,17],[1243,346,17],[1218,378,16],[1200,401,17],[1170,435,17],[1160,447,17],[1153,457,20],[1145,470,24],[1143,474,30],[1143,475,27],[1140,477,34],[1138,477,16],[1138,477,14]]);
await map.wheel([[1080,352,-100,0],[1080,347,-100,33],[1081,345,-100,34],[1081,345,-100,50]]);
await endHidden();
// ── Shown again ──
await map.view(60.8417325, 11.185627, 15);
await map.click(60.8449942, 11.1966991);

// ── Hidden from the video ──
await startHidden();
await map.wheel([[1058,351,100,0],[1058,351,100,55],[1058,351,100,65],[1060,358,100,67],[1075,376,100,50]]);
await map.drag([[1220,653,0],[1220,651,54],[1217,646,17],[1206,631,18],[1187,611,24],[1173,597,17],[1158,583,17],[1141,564,18],[1122,546,24],[1112,534,17],[1102,521,17],[1090,508,17],[1070,486,16],[1061,475,18],[1037,447,24],[1012,414,25],[1001,399,17],[979,372,17],[967,359,17],[942,335,25],[930,325,17],[920,318,17],[911,312,25],[910,311,17],[905,310,11]]);
await map.wheel([[1106,569,100,0],[1106,569,100,30],[1106,570,100,53],[1111,578,100,59]]);
await map.drag([[1182,634,0],[1181,631,30],[1177,627,17],[1168,621,17],[1159,613,17],[1144,601,17],[1128,588,16],[1116,576,17],[1108,567,17],[1098,558,17],[1092,549,17],[1087,543,17],[1082,536,17],[1077,530,17],[1074,527,17],[1069,524,17],[1064,521,16],[1058,518,17],[1054,517,17],[1050,515,17],[1042,512,17],[1040,511,17],[1038,510,17],[1036,508,17],[1031,503,16],[1026,500,17],[1020,494,17],[1012,488,17],[999,479,17],[985,473,17],[977,468,17],[976,468,15]]);
await map.wheel([[999,516,-100,0],[999,516,-100,52],[999,516,-100,68],[999,514,-100,84],[1061,556,-100,277],[1061,556,-100,30],[1061,556,-100,60]]);
await endHidden();
// ── Shown again ──
await map.view(60.7995723, 11.264205, 15);
await map.click(60.7960547, 11.2708139);
await page.getByRole('button', { name: 'Done' }).click();

// ── Hidden from the video ──
await startHidden();
await map.wheel([[1153,803,100,0],[1153,803,100,142],[1153,803,100,92],[1153,803,100,134],[1153,803,100,191]]);
await map.view(60.818138, 11.2187576, 13);
await map.drag([[921,767,0],[920,766,16],[920,763,29],[919,756,23],[919,748,16],[919,728,24],[919,715,17],[919,701,17],[919,680,17],[923,665,17],[925,653,17],[927,643,17],[929,638,17],[930,631,17],[931,631,119],[933,632,23],[934,633,17],[936,636,17],[938,640,17],[940,642,17],[942,648,17],[942,650,113]]);
await map.view(60.8083437, 11.2151527, 13);
await map.wheel([[900,644,100,0]]);
await map.drag([[898,635,0],[896,633,53],[895,629,18],[892,623,17],[884,610,17],[881,604,17],[877,595,17],[875,589,17],[874,586,17],[873,582,17],[873,582,127]]);
await map.view(60.8109391, 11.2067413, 12);
await endHidden();
// ── Shown again ──

// ── Phase: Unknown leg 1 ──
await chapter("Unknown leg 1");
await say("Next, add an unknown leg. Click Add, then click the backbone waypoint the contestants must find. They only get a photo of it.", { wait: false });
await page.getByRole('button', { name: 'Add' }).first().click();
await map.click(60.752786, 11.1593249);
await say("From the unknown waypoint, you now draw the dummy leg. It is shown on the contestants' map, and hides where the unknown waypoint really is.", { wait: false });
await map.click(60.7299652, 11.1847687);
await page.getByRole('button', { name: 'View' }).click();
await map.drag([[737,991,0],[736,991,157],[734,991,158],[732,991,97],[731,992,19],[730,993,221],[728,993,21],[728,994,580]]);
await map.drag([[728,994,0],[729,994,83],[730,994,45],[731,994,53],[732,994,38],[733,994,23],[734,994,37],[735,994,45],[736,994,67],[736,994,204]]);
await map.click(60.7299652, 11.1827087);

// ── Phase: Unknown leg 2 ──
await chapter("Unknown leg 2");
await say("Do the same for the second unknown leg.", { wait: false });
await map.view(60.8106042, 11.2077713, 12);
// A click on the map in View mode closes the wizard's guide, which has the Add buttons: open it again
await page.getByRole('button', { name: 'Task Wizard' }).click();
await page.getByRole('button', { name: 'Add' }).first().click();
await map.click(60.821988, 11.1661983);
await map.click(60.8440743, 11.1411667);
await map.drag([[606,307,0],[607,307,82],[607,306,80],[609,306,63],[610,306,19],[611,306,25],[612,306,121],[613,306,22],[613,306,271]]);
await map.view(60.8104368, 11.205368, 12);
await page.getByRole('button', { name: 'View' }).click();
await map.drag([[609,309,0],[609,307,120],[609,306,26],[611,305,109],[612,305,38],[612,304,20],[613,304,17],[614,304,143],[615,304,22],[615,304,234]]);
await page.getByRole('button', { name: 'Done' }).click();

// ── Phase: Add hidden ──
await chapter("Add hidden");
await say("To make the route harder, add hidden gates anywhere along it, even on the leg after an unknown waypoint.", { wait: false });
await page.getByRole('button', { name: 'Task Wizard' }).click();
await page.getByRole('button', { name: 'Add' }).nth(2).click();
await map.wheel([[815,808,-100,0]]);
await map.wheel([[689,771,-100,0]]);
await map.wheel([[634,697,-100,0]]);
await map.view(60.7701843, 11.1912918, 15);
await map.click(60.7714207, 11.1857128);
await map.wheel([[720,539,100,0],[720,539,100,116],[723,550,100,125],[726,556,100,100],[726,557,100,92],[727,557,100,100],[729,558,100,159]]);
await map.view(60.7772667, 11.2132645, 12);
await map.wheel([[726,172,-100,0],[726,172,-100,87],[700,170,-100,325],[689,173,-100,283]]);
await map.view(60.8264232, 11.1872149, 15);
await map.drag([[701,279,0],[702,279,27],[702,280,48],[702,282,19],[701,286,17],[699,291,17],[692,307,17],[691,310,17],[679,335,17],[673,348,17],[666,366,17],[660,383,17],[655,402,17],[649,424,17],[646,436,17],[639,467,17],[631,497,17],[626,513,17],[621,531,17],[606,570,17],[600,586,17],[594,602,17],[587,621,17],[580,640,17],[568,668,17],[559,687,17],[551,704,17],[543,721,17],[530,748,17],[527,756,16],[524,761,16],[521,766,17],[521,766,144]]);
await map.view(60.8366093, 11.1949396, 15);
await map.click(60.8395579, 11.1895752);
await page.getByRole('button', { name: 'Done' }).click();
await map.wheel([[1033,161,100,0],[1033,161,100,213],[1033,161,100,142]]);
await map.view(60.8148736, 11.1650276, 13);
await map.drag([[978,474,0],[977,474,28],[976,473,25],[971,465,17],[968,458,17],[960,445,17],[950,427,17],[942,411,16],[933,389,17],[928,378,16],[924,367,17],[921,358,17],[916,341,16],[914,334,17],[913,329,17],[912,324,17],[910,318,17],[908,314,17],[907,311,17],[907,310,19],[907,310,151]]);
await map.view(60.8011426, 11.1772156, 13);

// ── Phase: Add curve ──
await chapter("Add curve");
await say("Legs can also be curved. Click the waypoint at the end of the leg, press Make Curved, and drag the curve into shape.", { wait: false });
await map.drag([[649,664,0],[649,663,37],[650,660,21],[653,646,17],[655,636,17],[658,621,17],[659,606,17],[661,583,17],[661,572,17],[661,558,17],[661,546,17],[661,535,17],[661,517,17],[661,512,17],[661,503,17],[661,493,17],[660,483,17],[659,473,17],[659,469,17],[659,464,17],[659,463,116]]);
await map.view(60.7843057, 11.175499, 13);
await map.click(60.7522828, 11.1588478);
await page.getByRole('button', { name: 'Make Curved' }).click();
await map.drag([[584,605,0],[583,605,52],[582,605,21],[575,606,17],[569,607,17],[561,610,17],[554,613,17],[546,616,17],[538,619,17],[535,621,17],[532,623,17],[528,626,17],[524,627,17],[517,631,22],[511,635,23],[503,640,22],[496,644,17],[492,647,17],[482,652,17],[476,654,17],[468,658,16],[459,662,17],[455,664,17],[451,666,17],[445,668,17],[437,671,16],[432,673,17],[429,674,17],[426,675,17],[424,676,17],[421,677,17],[418,678,20],[415,679,23],[412,681,24],[408,683,17],[402,684,17],[399,686,17],[396,687,17],[394,688,17],[393,688,17],[392,689,19],[391,689,158],[388,690,23],[386,691,17],[384,691,33],[384,691,190]]);
await map.drag([[1011,955,0],[1011,951,37],[1009,948,17],[1008,946,17],[1007,940,17],[1006,936,17],[1003,930,17],[1001,925,25],[999,919,17],[996,913,17],[993,903,17],[992,897,17],[990,891,17],[988,885,26],[986,874,16],[985,867,17],[983,857,17],[983,848,17],[982,834,17],[982,823,17],[982,813,17],[982,802,17],[982,794,17],[982,786,17],[982,780,17],[981,775,17],[981,771,17],[981,767,16],[980,765,17],[980,762,21],[980,761,21],[978,757,17],[978,752,17],[976,749,17],[975,744,17],[975,741,17],[973,737,17],[973,736,112]]);
await map.view(60.7659509, 11.1820229, 13);
await map.click(60.7289581, 11.1850969);
await page.getByRole('button', { name: 'Make Curved' }).click();
await say("Curving the dummy leg as well gives one smooth curve, with the unknown waypoint hidden somewhere along it.", { wait: false });
await map.drag([[739,805,0],[737,805,16],[731,805,24],[724,808,17],[715,810,17],[704,814,17],[700,817,17],[696,819,17],[692,822,17],[690,824,17],[688,825,17],[685,826,17],[684,827,19],[679,832,23],[674,834,17],[671,836,17],[669,837,17],[669,837,161]]);
await map.drag([[815,947,0],[815,946,105],[816,944,26],[818,942,17],[820,940,17],[823,934,17],[826,932,17],[828,928,17],[831,925,17],[834,922,17],[836,919,17],[840,916,17],[845,911,17],[850,907,17],[856,901,17],[860,898,17],[862,895,17],[864,892,17],[868,888,17],[871,885,17],[876,880,17],[881,876,17],[885,871,17],[891,865,17],[896,860,17],[899,855,17],[905,848,17],[912,838,17],[922,825,17],[928,818,16],[939,806,17],[945,800,16],[956,782,17],[961,775,17],[964,770,17],[966,765,17],[968,760,17],[970,753,17],[971,749,17],[971,745,16],[973,739,17],[973,735,17],[973,731,17],[975,726,16],[976,720,17],[976,712,17],[976,709,17],[976,707,50],[976,703,17],[977,703,96],[977,702,309]]);
await map.drag([[831,599,0],[832,599,82],[832,600,30],[832,608,23],[833,618,30],[833,625,16],[833,632,17],[834,637,17],[834,644,17],[835,653,17],[836,658,17],[837,663,17],[837,669,17],[838,673,17],[838,679,17],[838,681,17],[838,686,17],[839,687,17],[839,690,17],[839,692,17],[839,696,21],[839,702,38],[839,704,17],[839,708,17],[839,711,17],[839,716,17],[838,719,17],[838,719,112]]);
await map.drag([[838,719,0],[838,720,68],[838,721,60],[838,722,51],[838,723,24],[838,725,34],[838,727,33],[838,727,196]]);
await map.click(60.7469984, 11.1885306);
await map.click(60.7468307, 11.1885306);

// ── Phase: Save ──
await chapter("Save");
await say("Finally, save the route.", { wait: false });
await page.getByRole('textbox', { name: 'Route Name' }).click();
await page.getByRole('textbox', { name: 'Route Name' }).fill("Task 2.A5 Unknown legs");
await page.getByRole('button', { name: 'Save Route' }).click();
// A dialog asks "Route has validation errors. Save anyway?": the recording accepts it
await map.view(60.797332, 11.1942315, 12);

// ── Hidden from the video ──
await startHidden();
await page.getByRole('link', { name: 'Back' }).click();
await page.getByRole('searchbox', { name: 'Search routes by name' }).click();
// The full name: other routes contain "unkn" too, so the list order would decide which one gets the task
await page.getByRole('searchbox', { name: 'Search routes by name' }).fill("Task 2.A5 Unknown legs");
await page.getByRole('button', { name: 'Create task' }).first().click();
await page.locator('.my-react-select__input-container').click();
await page.getByRole('option', { name: '2.A5 Navigation with unknown legs', exact: true }).click();
await page.locator('.my-react-select__input-container').click();
await page.getByRole('option', { name: 'Tutorial contest' }).click();
await page.getByRole('textbox', { name: 'Name' }).click();
await page.getByRole('textbox', { name: 'Name' }).fill("Task 2.A5 Unknown legs");
// Chosen in the browser's date picker when the clicks were recorded, which the recorder did not see: today, 09:00 to 18:00
const today = new Date().toLocaleDateString("sv-SE");
await page.getByRole('textbox', { name: 'Start time' }).fill(`${today}T09:00`);
await page.getByRole('textbox', { name: 'Finish time' }).fill(`${today}T18:00`);
await page.locator('div').filter({ hasText: /^Create navigation task$/ }).click();
await page.getByRole('checkbox', { name: 'Allow self-management Lets' }).click();
await page.getByRole('checkbox', { name: 'Allow observation' }).click();
await page.getByRole('button', { name: 'Create navigation task' }).click();
await page.getByRole('button', { name: 'Continue' }).click();
await page.getByRole('link', { name: 'Live Map' }).click();
await map.view(60.7975776, 11.175991, 12);

// ── Hidden from the video ──
await startHidden();
await map.click(60.8567837, 11.3090515);
await map.wheel([[976,396,-100,0]]);
await map.wheel([[976,396,100,0]]);
await map.view(60.7975414, 11.1758423, 12);
await page.getByRole('button', { name: 'Settings' }).click();
await page.getByRole('checkbox', { name: 'Show Secret Gates' }).click();
await page.getByRole('checkbox', { name: 'Show Secret Gates' }).click();
await page.getByText('SettingsShow Background').click();
await page.getByRole('link', { name: 'Manage' }).click();
await page.getByText('Manage', { exact: true }).click();
await page.getByRole('link', { name: 'Manage photos' }).click();
await map.view(60.7975776, 11.175991, 12);
await page.getByRole('link', { name: 'Back to navigation task' }).click();
await page.getByRole('link', { name: 'Back to contest' }).click();
await page.getByRole('link', { name: 'Task 2.A5 Unknown legs' }).click();
await page.getByRole('link', { name: 'Live Map' }).click();
await map.view(60.7975776, 11.175991, 12);

await endHidden();
// ── Shown again ──

// ── Phase: Live map ──
await chapter("Live map");
await say("The live map shows the whole route the contestants will fly, dummy legs included.", { wait: false });
await map.wheel([[672,380,-100,0]]);
await map.view(60.8087623, 11.1264038, 13);
await map.drag([[707,403,0],[706,401,73],[681,369,23],[669,353,17],[659,338,33],[645,315,33],[629,280,22],[619,258,20],[616,249,25],[606,229,17],[590,193,22],[588,189,20],[585,181,17],[580,171,33],[578,169,25],[575,162,17],[571,157,17],[570,156,25],[569,156,67],[569,155,42],[566,151,33],[565,149,19],[562,146,23],[560,143,17],[554,134,17],[553,132,25],[552,130,17],[549,125,17],[549,125,21]]);
await map.view(60.7853111, 11.153698, 13);
await say("Turn off the secret gates, and you see the map the contestants get: the dummy legs are drawn, but the unknown legs are not.", { wait: false });
await page.getByRole('button', { name: 'Settings' }).click();
await page.getByRole('checkbox', { name: 'Show Secret Gates' }).click();
await map.wheel([[517,444,100,0]]);
await map.view(60.7794456, 11.229744, 12);

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
