// NILTV web — environment config.
// Dev stack (niltv-dev). Must be the CloudFront domain: the API only answers
// through CloudFront.
window.NILTV_CONFIG = {
  apiBase: "https://d1nm1d2txb83wa.cloudfront.net",
  // Lambda function URL for /payouts/start (niltv-payouts-start, us-east-1).
  // Empty until the function URL is created; the page shows "not live yet".
  payoutsApi: "https://7xmxwsdz6jjxdnnp32yyepu4ui0faomc.lambda-url.us-east-1.on.aws/",
  // Athlete signup intake: the dashboard API's public POST /api/applications/
  // (niltv-dashboard, applications router; CORS allows this origin). Empty =
  // the /athlete-signup/ form runs in demo mode and shows the payload instead.
  applicationsApi: "https://api-dev.niltv.com/api/applications/",
  cognito: {
    // niltv-dev pool + the niltv-dev-web client (SRP, no secret - browser
    // safe). deploy.ps1 -Env prod writes the prod pool and client instead.
    userPoolId: "us-east-1_fxm8vObBQ",
    clientId: "69hvk5aatjjcsij0ian5n72n23",
  },
};
