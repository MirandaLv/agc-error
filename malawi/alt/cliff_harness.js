var http = require('http');
var request = require("sync-request");
var lazy = require("lazy");
var fs = require('fs');
var path = require('path')



var autocoderURL = process.argv[2]; 	//directory of files to process; required
var directory = process.argv[3]; 		//autocoderurl; required
var limitto = process.argv[4];      	//the geoname id of the country to limit your results to; optional

//we need at least the csvfile
if (!directory || !autocoderURL)
{
	console.log ("Missing Required Parameters, example:");
    console.log("node cliff_harness.js http://localhost:8999/CLIFF-2.0.0/parse/text?q= directory_of_files");
	process.exit(1);
}

//simple cleaning function
function cleanText (text)
{
	text = text.replace(/[‘.','"%]/g," ");
 	return text;
}

function arrayContains(arr, val, equals) {
    var i = arr.length;
    while (i--) {
        if ( equals(arr[i], val) ) {
            return true;
        }
    }
    return false;
}

function removeDuplicates(arr, equals) {
    var originalArr = arr.slice(0);
    var i, len, j, val;
    arr.length = 0;

    for (i = 0, len = originalArr.length; i < len; ++i) {
        val = originalArr[i];
        if (!arrayContains(arr, val, equals)) {
            arr.push(val);
        }
    }
    return arr;
}


function thingsEqualId(thing1, thing2) {
    return thing1.id === thing2.id;
}

function thingsEqualGID(thing1, thing2) {
    return thing1.geonameId === thing2.geoNameId;
}

function findinArray(geonames,id)
{
	r = 0;
	while( r <geonames.length )
	{
		if (geonames[r].id === id)
			return true;
		r++;
	}
	return false;
}
function getCountryCode(id)
{
	var res = request('GET', "http://api.geonames.org/getJSON?formatted=true&geonameId="+id+"&username=jpowell");
	var info = res.getBody().toString('utf8');
	var rz = JSON.parse(info);
	return rz.countryCode;
}

function getHeirarchy (id)
{
	var res = request('GET', "http://api.geonames.org/hierarchyJSON?formatted=true&geonameId="+id+"&username=jpowell");
	var info = res.getBody().toString('utf8');
	var rz = JSON.parse(info);
	var arr = new Array();
	
	for (var c = 0; c < rz.geonames.length; c++)
	{
		arr.push(rz.geonames);	
	}
	return arr;
}
function idNotInHeir(heirarch, id)
{
	t = 0;
	//console.log("Looking for: "+id);
	while (t < heirarch.length)
	{
		if (heirarch[t].geonameId == id)
		{
			return false;
		}
		t++;
	}
	return true;
}

function updateHeir(heirarch, id)
{
	thisHeir = getHeirarchy(id);
	for (var e = 0; e < thisHeir.length; e++)
	{
		for (var f = 0; f < thisHeir[e].length; f++)
		{
			heirarch.push(thisHeir[e][f]);
		}
	}
	heirarch = removeDuplicates(heirarch,thingsEqualGID);
	return heirarch;
}

//callback for file read
function onReadfile(err,data)
{
	codeit(data);
}

//the codeit function--most of the magic happens in here
function codeit(data)
{
	text = cleanText(data.toString());
	tokens = text.split(' ');

	x = 0;
	var geonames = new Array();
	var heirarch = new Array();
	
	while (x < tokens.length)
	{
		toclass ='';
		while (toclass.length < 1500 )
		{
			toclass +=tokens[x]+' ';
			x++;
		}
		var bf = false;
		res = request('GET', autocoderURL + toclass);
		info = res.getBody().toString('utf8');
		rz = JSON.parse(info);
		if (rz && rz.status != 'error')
		{
		
			/*APPROACH: We Build our locations from most focused to least focused
			1) Use all the 'focus cities' from CLIFF
			2) Use all the 'focus states' from CLIFF, less those that appear up the hierarchy from our 2)
			3) Use all the 'focus countries' from CLIFF, less those that appear up the hierarchy from 1) and 2)
			4) Use all the 'mentions' from CLIFF, less those that appear up the hierarchy from 1) and 2) and 3)
			5) Create unique list of these locations and output them
			*/
		
			if (rz.results.places.focus)
			{
				//paint cities on (step 1)
				if (rz.results.places.focus.cities)
				{
					for (var r = 0; r < rz.results.places.focus.cities.length; r++)
					{
					
						if (!limitto || (rz.results.places.mentions[r].countryCode == countryCode))
						{
							//we add ALL the focus cities
							heirarch = updateHeir(heirarch, rz.results.places.focus.cities[r].id);
							rz.results.places.focus.cities[r].type = 'focus-cities';
							geonames.push(rz.results.places.focus.cities[r]);
						}	
					}
				}
			
				//paint states on (step 2)
				if (rz.results.places.focus.states)
				{
					for (var r = 0; r < rz.results.places.focus.states.length; r++)
					{
						//if this state is not in our current heirarchy, include it
						if (idNotInHeir(heirarch, rz.results.places.focus.states[r].id) && (!limitto || (rz.results.places.focus.states[r].countryCode == countryCode)))
						{
							heirarch = updateHeir(heirarch, rz.results.places.focus.states[r].id);
							rz.results.places.focus.states[r].type = 'focus-states';
							geonames.push(rz.results.places.focus.states[r]);
						}
					}		
				}
				
				//paint countries on (step 3)
				if (rz.results.places.focus.countries)
				{
					for (var r = 0; r < rz.results.places.focus.countries.length; r++)
					{				
						//if this state is not in our current heirarchy, include it
						if (idNotInHeir(heirarch, rz.results.places.focus.countries[r].id) && (!limitto || (rz.results.places.focus.countries[r].countryCode == countryCode)))
						{
							heirarch = updateHeir(heirarch, rz.results.places.focus.countries[r].id);
							rz.results.places.focus.countries[r].type = 'focus-countries';
							geonames.push(rz.results.places.focus.countries[r]);
						}
					}
				}
			}
		
			//paint mentions on (step 4)
			for (var r = 0; r < rz.results.places.mentions.length; r++)
			{
				//if this state is not in our current heirarchy, include it
				if (idNotInHeir(heirarch, rz.results.places.mentions[r].id) && (!limitto || (rz.results.places.mentions[r].countryCode == countryCode)))
				{
					heirarch = updateHeir(heirarch, rz.results.places.mentions[r].id);
					rz.results.places.mentions[r].type = 'mention';
					geonames.push(rz.results.places.mentions[r]);
				}
			}	
		}		
	}

	//make unique and output (step 5)
	if (geonames.length > 0)
	{
		uniqueArray = removeDuplicates(geonames, thingsEqualId);
		//output the final array of locations
		for (var t = 0; t < uniqueArray.length; t++)
		{
			console.log(uniqueArray[t].type+", "+uniqueArray[t].id+", "+uniqueArray[t].lat+", "+uniqueArray[t].lon);	
		}
	}
}

//main application
if (limitto)
	var countryCode = getCountryCode(limitto);
	
console.log('type, geonameid, lat, lng');

//read the files and code them; read the files line by line
files = fs.readdirSync(directory);
for (var f = 0; f < files.length; f++)
{
	var filename = directory+'/'+files[f];
	
	var ext = path.extname(filename).toLowerCase();
	if (ext.toLowerCase() == '.csv')
	{
		new lazy(fs.createReadStream(filename))
		 .lines
		 .forEach(function(line){
			 codeit(line.toString());
		 });
	}
	else
	{
		fs.readFile(filename, onReadfile);
	}
}


