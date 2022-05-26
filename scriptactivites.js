
const degs2Rads = deg => (deg * Math.PI) / 180.0;

const rads2Degs = rad => rad * 180 / Math.PI;

function getBounds(lat, lng,distance=1) {
    const earthRadius = 6371
    const response = {}
    const cardinalCoords = {
        north: 0,
        south: 180,
        east: 90,
        west: 270
    }
    
    const rLat = degs2Rads(lat);
    const rLng = degs2Rads(lng);
    const rAngDist = distance/earthRadius;
    for (const [name, angle] of Object.entries(cardinalCoords)) {
        
        const rAngle = degs2Rads(angle);
        const rLatB = Math.asin(Math.sin(rLat) * Math.cos(rAngDist) + Math.cos(rLat) * Math.sin(rAngDist) * Math.cos(rAngle));
        const rLonB = rLng + Math.atan2(Math.sin(rAngle) * Math.sin(rAngDist) * Math.cos(rLat), Math.cos(rAngDist) - Math.sin(rLat) * Math.sin(rLatB));

        response[name] = {
            'lat' : rads2Degs(rLatB), 
            'lng' : rads2Degs(rLonB)
        };
    }
    return {
        'min_lat'  : response['south']['lat'],
        'max_lat' : response['north']['lat'],
        'min_lng' : response['west']['lng'],
        'max_lng' : response['east']['lng']
    }
}

const getActivitiesInTheArea = async (req,res,next) =>{
    
    const {distance=5,country} = req.query
    var Numberitems = 0
    var numberitemsInPage= 50
    var pageNumber = 0
    var search ={
        city:{$exists:true},
        state:{$exists:true},
    }
    if(country){
        search['$or']=[
            {country: {$regex: query, $options: 'i'}},
            {countryEn: {$regex: query, $options: 'i'}}
        ]
    }
    const totalItems = await citymodel.countDocuments(search)
    try {
        
        while (Numberitems<totalItems) {
            const resultdb = await citymodel.find(search).skip(pageNumber*numberitemsInPage).limit(numberitemsInPage)
            for(const city of resultdb) {
                
                const bounds = getBounds(parseFloat(city.lat), parseFloat(city.lon),distance)
                const searchObj ={
                    lat: {$gte: bounds['min_lat'], $lte: bounds['max_lat']},
                    lon: {$gte: bounds['min_lng'], $lte: bounds['max_lng']},
                }
                console.log(city.fullName)
                const activites = await  adminPlace.find(searchObj, {urlImg:1,location:1,name:1,_id:1})
                for(const activity of activites){
                    const location = activity.location.map(ac=>`${ac._id}`)
                    console.log(activity.name)
                    location.push(`${city._id}`)
                    activity.location =  _.uniq(location)
                    await activity.save()
                }
                const numberActi = await adminPlace.countDocuments({
                    location:city._id,
                    $and:[
                        {$or:[{hide:{$exists: false}}, {hide:false}]},
                        {$or:[{incomplete:{$exists: false}}, {incomplete:false}]}
                    ]
                })
                const activitiesImg = await  adminPlace.find({
                    location:city._id, 
                    $and:[
                        {$or:[{hide:{$exists: false}}, {hide:false}]},
                        {$or:[{incomplete:{$exists: false}}, {incomplete:false}]}
                    ], urlImg:{$exists: true}}, {urlImg:1}).limit(3).sort({stars: -1, _id:1})
                city.cityActivities= activitiesImg.map(act=>act.urlImg)
                city.numberActivities = numberActi
                await city.save()
                //aqui se guardaria dentro del nuevo arreglo o algo asi
            }
            ++pageNumber
            Numberitems = Numberitems + resultdb.length
        }
        res.json({
            error: false,
        })
    } catch (error) {
        console.log(error)
        next(new Error(error))
    }
}