/*
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
var configObj = {
  "enableDebug": false,
  "invalidateCache": false,
  "accounts": {
    "dummyname": {
      "issuer": "<<REPLACE THIS WITH YOUR BTP XSUAA SERVICE KEY URL>>",
      "publicKey": "<<REPLACE THIS WITH YOUR BTP XSUAA SERVICE KEY VERIFICATIONKEY>>",
      "destinationName": "<<REPLACE THIS WITH YOUR DESTINATION NAME. For example, apim-user-token-exchange-destination>>",
      "destinationUri": "<<REPLACE THIS WITH YOUR DESTINATION PLAN LITE SERVICE KEY URI WITHOUT https://>>",
      "destinationAuthEndpoint": "<<REPLACE THIS WITH YOUR DESTINATION PLAN LITE SERVICE KEY URL WITHOUT https://>>",
      "destinationClientId": "<<REPLACE THIS WITH YOUR DESTINATION PLAN LITE SERVICE KEY CLIENTID>>",
      "destinationClientSecret": "<<REPLACE THIS WITH YOUR DESTINATION PLAN LITE SERVICE KEY CLIENTSECRET>>"
    }
  }
}

context.setVariable("myVar.debug.enable", configObj["enableDebug"])

//check if the issuer of the incoming token is found in the configObj above
var eachAccountObj, issuerExpected, accountNameFound = null

for (var accountName in configObj["accounts"]) {
  eachAccountObj = configObj["accounts"][accountName]
  issuerExpected = eachAccountObj["issuer"]
  if (issuerExpected !== context.getVariable("jwt.dcodejwt.claim.issuer")) {
    continue
  }
  accountNameFound = accountName
  context.setVariable("myVar.accountNameFound", accountNameFound)
  context.setVariable("myVar.jwt.issuer", issuerExpected)
  context.setVariable("myVar.jwt.publicKey", eachAccountObj["publicKey"])
  context.setVariable("myVar.destination.clientId", eachAccountObj["destinationClientId"])
  context.setVariable("myVar.destination.clientSecret", eachAccountObj["destinationClientSecret"])
  context.setVariable("myVar.destination.authEndpoint", eachAccountObj["destinationAuthEndpoint"])
  context.setVariable("myVar.destination.uri", eachAccountObj["destinationUri"])
  context.setVariable("myVar.destination.name", eachAccountObj["destinationName"])

  break;
}


/*
Expected cache payload
{
  "usa": {
    "destToken": "","generatedTime":123123,"tokenValidTillTime": 321
  }
}
*/

if (accountNameFound != null) {

  //transform cacheString to cacheObj
  var cacheObj = {},
    doQueryForFreshToken = "y"
  var cacheString = context.getVariable("myVar.cacheResponseString")

  if ((cacheString === null) || (cacheString === undefined) || (cacheString === "") || (configObj["invalidateCache"] === true)) {
    doQueryForFreshToken = "y"

  } else {
    cacheObj = JSON.parse(cacheString)
    if (accountNameFound in cacheObj) {
      //check if the token is still valid
      if (cacheObj[accountNameFound]["tokenValidTillTime"] > context.getVariable("system.timestamp")) {
        doQueryForFreshToken = "n"
        context.setVariable("myVar.destination.resp.access_token", cacheObj[accountNameFound]["destToken"])
      }
    }
  }

  context.setVariable("myVar.destination.doQueryForFreshToken", doQueryForFreshToken)
}