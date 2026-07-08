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
if (context.getVariable("myVar.destination.doQueryForFreshToken") === "y") {
    
  var accountNameFound = context.getVariable("myVar.accountNameFound")
  var cacheObj = {},
    cacheString = context.getVariable("myVar.cacheResponseString")
  if ((cacheString === null) || (cacheString === undefined) || (cacheString === "")) {
    cacheObj = {}
  } else {
    cacheObj = JSON.parse(cacheString)
  }
  cacheObj[accountNameFound] = {}
  cacheObj[accountNameFound]["destToken"] = context.getVariable("myVar.destination.resp.access_token")
  cacheObj[accountNameFound]["generatedTime"] = context.getVariable("system.timestamp") 
  cacheObj[accountNameFound]["tokenValidTillTime"] = cacheObj[accountNameFound]["generatedTime"]+ (context.getVariable("myVar.destination.resp.access_token_expiry")*1000)


  var str = JSON.stringify(cacheObj)
  context.setVariable("myVar.cacheString", str)

}

//massage token 
var finalToken = context.getVariable("myVar.destination.resp.finalToken")
context.setVariable("request.header.Authorization", "Bearer " + finalToken)