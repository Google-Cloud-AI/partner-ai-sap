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
var staticVariableMap={
    "AccountNameIdentified":"myVar.accountNameFound",
    "Destination_Auth_Endpoint":"myVar.destination.authEndpoint",
    "Destination_Auth_ClientId":"myVar.destination.clientId",
    "Destination_Auth_Uri":"myVar.destination.uri",
    "Destination_Name":"myVar.destination.name",
    "QueryFreshRefreshToken":"myVar.destination.doQueryForFreshToken",
    "CacheResponseAtStart":"myVar.cacheResponseString",
    "CacheResponseAtEnd":"myVar.cacheString"

    }
    
var dynamicVariableMap={
    "IncomingAuthToken":"myVar.incoming.loginToken",
    "Base64EncodedDestinationServiceCred":"myVar.destination.encodedBasicAuth",
    "Destination_Service_access_token":"myVar.destination.resp.access_token",
    "Final Token required for API Proxy":"myVar.destination.resp.finalToken"

}

var finalJson={}
finalJson["static"]=getJson(staticVariableMap)
finalJson["dynamic"]=getJson(dynamicVariableMap)


var rc = context.getVariable("response.content");
context.setVariable("response.content", JSON.stringify(finalJson));
context.setVariable("response.header.Content-Type'", 'application/json');

//context.setVariable("response.content", finalJson);


function getJson(myMap){
    var j={},value=0
    for (var m in myMap){
        
        try{
            value=JSON.parse(context.getVariable(myMap[m]))
        }catch(e){
            value=context.getVariable(myMap[m])
        }
        j[m]=value
    }
    return j
    
}
    
