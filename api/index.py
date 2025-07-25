from flask import Flask, request
from pymongo import MongoClient
from datetime import datetime

import os

MONGO_URI = os.getenv("MONGO_URI")  # or whatever name you choose


app = Flask(__name__)
client = MongoClient(MONGO_URI)
# client = MongoClient("mongodb://localhost:27017/")
db = client.chatdb

import hashlib

def generate_id(name: str, username: str, length: int = 12) -> str:
    
    input_string = f"{name.strip().lower()}::{username.strip().lower()}"
    
    # Create a SHA-256 hash of the combined string
    hash_digest = hashlib.sha256(input_string.encode()).hexdigest()
    
    # Return the first `length` characters of the hash
    return hash_digest[:length]


@app.route("/send", methods=["POST"])
def receive_data():
    data = request.json
    mode = data.get("mode")
    user_id = data.get("user_id")
    if mode == "courseadd":
        course_id = 'C_' + generate_id(data["name"], user_id)
        db.courses.insert_one({
            "creator" : user_id,
            "courseID" : course_id,
            "author_name" : data["author_name"],
            "name" : data["name"],
            "parent" : data["parent"], #parent subject of the course, generated by AI
            
        })

        db.explorer.insert_one({
            "user_id": user_id,
            "courseID": course_id,
            "is_public" : False,
        })
        return{"status": "success"}, 200
    
    elif mode == "courseadd2":
        db.explorer.insert_one({
            "user_id": user_id,
            "courseID": data["courseID"],
            "is_public" : False,
        })
        return{"status": "success"}, 200

    elif mode == "chatadd":
        db.messages.insert_one({
            "Sender": user_id,
            "Receiver": data["receiver"],
            "Message": data["message"],
            "Timestamp": datetime.fromisoformat(data["timestamp"])
        })
        return {"status": "chat saved"}, 200
    
    elif mode == "flashadd":
        db.flashcards.insert_one({
            "Creator": user_id,
            "FlashcardID": 'F_' + data["course"] +'_'+ str(db.flashcards.count_documents({"Course": data['course']})+1) ,
            "Course": data["course"],
            "Content": data["content"],
            "Read" : 0
        })
        return{"status": "success"}, 200

    elif mode == "quesadd":
        db.questions.insert_one({
            "Creator": user_id,
            "Course": data["course"],
            "QuestionID": 'Q_'+ data['course'] +'_'+ str(db.questions.count_documents({"Course": data['course']})+1),
            "Question": data["question"],
            "Option1": data["option1"],
            "Option2": data["option2"],
            "Option3": data["option3"],
            "Option4": data["option4"],
            "Correct": data["ans"],
            "Explanation" : data["explanation"],
            "Solved" : 0
        })
        return{"status": "success"}, 200
    
    elif mode == "articleadd":
        db.articles.insert_one({
            "Creator": user_id,
            "Article" : 'A_' +data["course"]+"_"+ generate_id(data["title"], user_id),
            "Course": data["course"],
            "Title" : data["title"],
            "Content" : data["content"],   # Subject to change
            "Read" : 0
        })  
        return{"status": "success"}, 200
    
    elif mode == "createstatus":
        db.status.insert_one({
            "Id": user_id,
            # "ProfComplete" : 0,
            # "PtsQs" : 0,
            # "PtsFlash" : 0,
            # "PtsRe" : 0,
            # "PtsEx" : 0,
            "PtsTotal" : 0
        })
        return{"status": "success"}, 200
    elif mode == "startactivity":
        db.activity.insert_one({
            "Id": user_id,
            "Day" : 0,
            "Is_logged_In" : 0,
            "Has_Attempted_Quiz" : 0,
            "Has_Viewed_Article" : 0,
            "Has_Viewed_Flash_Card" : 0,
            "Has_Completed_Course" : 0,
        })
    elif mode == "courseprogress":
        courseID = data["courseID"]
        course_progress = data["course_progress"]
        course = db.explorer.find_one({"courseID": courseID, "user_id": user_id})
        if not course:
            return {"error": "Course not found or not accessible"}, 403
        db.explorer.update_one({"_id": course["_id"]}, {"$set": {"course_progress": course_progress}})
        return {"status": "success"}, 200



@app.route("/get", methods = ['POST'])
def getData():
    data = request.json
    mode = data.get("mode")
    user_id = data.get("user_id")
    if mode == "statusget":
        status = db.status.find_one({"Id": user_id})
        if status:
            return {"status": status}, 200
        else:
            return {"error": "Status not found"}, 404
    elif mode == "courseget":
        courses = db.explorer.find({"user_id": user_id})
        course_list = []
        courseID_to_access_map = {}
        if not courses:
            return {"courses": []}, 200
        for course in courses:
            course_list.append(course["courseID"])
            courseID_to_access_map[course["courseID"]] = course.get("is_public", False)

        course_list = list(set(course_list))

        course_info = db.courses.find({"courseID": {"$in": course_list}})
        course_list = []
        for course in course_info:
            course_list.append({
                "creator": course["creator"],
                "courseID": course["courseID"],
                "name": course["name"],
                "author_name": course.get("author_name", ""),
                "access": courseID_to_access_map.get(course["courseID"], False),
                "parent": course["parent"]
            })
        return {"courses": course_list}, 200
    

    elif mode == "coursegetexplorer":
        # Find all public courses not created by the user and not already in user's explorer
        user_courses = set(course["courseID"] for course in db.explorer.find({"user_id": user_id}))
        public_courses_cursor = db.explorer.find({
            "user_id": {"$ne": user_id},
            "is_public": True,
            "courseID": {"$nin": list(user_courses)}
        })

        public_course_ids = [course["courseID"] for course in public_courses_cursor]

        if not public_course_ids:
            return {"courses": []}, 200

        course_info = db.courses.find({"courseID": {"$in": public_course_ids}})
        course_list = []
        for course in course_info:
            course_list.append({
                "creator": course["creator"],
                "courseID": course["courseID"],
                "name": course["name"],
                "author_name": course.get("author_name", ""),
                "parent": course["parent"]
            })
        return {"courses": course_list}, 200
    elif mode == "coursegetspec":
        courseID = data["courseID"]
        course = db.explorer.find_one({"courseID": courseID, "user_id": user_id})
        if not course:
            return {"error": "Course not found or not accessible"}, 403
        
        course2 = db.courses.find_one({"courseID": courseID})   
        
        if course2:  
            course_data = {
                "creator": course2["creator"],
                "courseID": course2["courseID"],
                "name": course2["name"],
                "author_name": course2.get("author_name", ""),
                "parent": course2["parent"]
            }
            return {"course": course_data}, 200

    elif mode == "chatget":
        times = data.get("count")
        messages = db.messages.find(
    {
        "$or": [
            {"Receiver": user_id},
            {"Sender": user_id}
        ]
    }).sort("Timestamp", -1).limit(times)
        messages_list = []
        for message in messages:
            messages_list.append({
                "Sender": message["Sender"],
                "Receiver": message["Receiver"],
                "Message": message["Message"],
                "Timestamp": message["Timestamp"].isoformat()
            })
        return {"messages": messages_list}, 200
    
    elif mode == "quesget":
        queslist = data["qlist"].split(",")
        print(queslist)
        questionlist = []
        for q1 in queslist:
            inval = 'Q_'+data["course"]+'_'+str(q1)
            print(inval)
            q = db.questions.find_one({"QuestionID": inval,"Course": data["course"], "Creator": user_id})
            if q:
                questionlist.append({
                    "Creator": q["Creator"],
                    "Course": q["Course"],
                    "QuestionID": q["QuestionID"],
                    "Question": q["Question"],
                    "Option1": q["Option1"],
                    "Option2": q["Option2"],
                    "Option3": q["Option3"],
                    "Option4": q["Option4"],
                    "Correct": q["Correct"],
                    "Explanation" : q["Explanation"]
                }) 
        return {"questions" : questionlist} , 200
    
    elif mode == "flashget":
        flashlist = data["flist"].split(",").strip()
        flashcardlist = []
        for f1 in flashlist:
            inval = 'F_'+data["course"]+'_'+str(f1)
            f = db.flashcards.find_one({"FlashcardID":inval ,"Course": data["course"], "Creator": user_id})
            if f:
                flashcardlist.append({
                    "Creator": f["Creator"],
                    "FlashcardID": f["FlashcardID"],
                    "Course": f["Course"],
                    "Content": f["Content"],
                    "Read" : f["Read"]
                }) 
        return {"flashcards" : flashcardlist} , 200
    
    elif mode == "articleget":
        articleID = data['articleID']
        articleID = 'A_'+data["course"]+'_'+str(articleID)
        article = db.articles.find_one({"Article": articleID})
        if article:
            article_data = {
                "Creator": article["Creator"],
                "Article": article["Article"],
                "Course": article["Course"],
                "Title": article["Title"],
                "Content": article["Content"],
                "Read" : article["Read"]
            }
            return {"article": article_data}, 200
        else:
            return {"error": "Article not found"}, 404
    elif mode == "getactivity":
        activity = db.activity.find_one({"Id": user_id})
        if activity:
            return {"activity": activity}, 200
        else:
            return {"error": "Activity not found"}, 404
    
    elif mode == "coursegetprogress":
        courseID = data["courseID"]
        course = db.explorer.find_one({"courseID": courseID, "user_id": user_id})
        if not course:
            return {"error": "Course not found or not accessible"}, 403
        
        progress = course.get("course_progress", {})
        
        response_progress = {
            "description_read": progress.get("description_read", 0),
            "flashcards_read": progress.get("flashcards_read", 0),
            "articles_read": progress.get("articles_read", 0),
            "quiz_score": progress.get("quiz_score", 0),
            "previous_answers": progress.get("previous_answers", ""),
        }
        return {"progress": response_progress}, 200

    elif mode == "coursegetprogressall":
        courses_cursor = db.explorer.find({"user_id": user_id})
        courses = list(courses_cursor)
        

        course_progress_list = []

        for course in courses:
            progress = course.get("course_progress", {})
            response_progress = {
                "description_read": progress.get("description_read", 0),
                "flashcards_read": progress.get("flashcards_read", 0),
                "articles_read": progress.get("articles_read", 0),
                "quiz_score": progress.get("quiz_score", 0),
                "previous_answers": progress.get("previous_answers", ""),
            }
            course_progress_list.append(response_progress)
        return {"course_progress_list": course_progress_list}, 200




@app.route("/process", methods = ['POST'])
def processData():
    data = request.json
    mode = data.get("mode")
    function = data.get("function")
    if mode == "quesprocess":
        if function == "solved":
            db.questions.update_one({"QuestionID": data["questionID"]}, {"$set": {"Solved": 1}})
            db.status.update_one({"Id": data["user_id"]}, {"$inc": {"PtsQs": 1,"PtsTotal": 1}})
            return {"status": "success"}, 200
        elif function == "mark":
            db.status.update_one({"Id": data["user_id"]}, {"$set": {"Has_Attempted_Quiz": 1}})
            return {"status": "success"}, 200
        
    elif mode == "flashprocess":
        if function == "read":
            db.flashcards.update_one({"FlashcardID": data["flashcardID"]}, {"$set": {"Read": 1}})
            db.status.update_one({"Id": data["user_id"]}, {"$inc": {"PtsFlash": 1,"PtsTotal": 1}})
            db.activity.update_one({"Id": data["user_id"]}, {"$set": {"Has_Viewed_Flash_Card": 1}})
            return {"status": "success"}, 200
    elif mode == "articleprocess":
        if function == "read":
            db.articles.update_one({"Article": data["articleID"]}, {"$set": {"Read": 1}})
            db.status.update_one({"Id": data["user_id"]}, {"$inc": {"PtsRe": 1,"PtsTotal": 1}})
            db.activity.update_one({"Id": data["user_id"]}, {"$set": {"Has_Viewed_Article": 1}})
            return {"status": "success"}, 200
    elif mode == "addextrapoints":
        if function == "extrapoints":
            db.status.update_one({"Id": data["user_id"]}, {"$inc": {"PtsEx": data["points"], "PtsTotal": data["points"]}})
            return {"status": "success"}, 200
    elif mode == "msgdelete":
        db.messages.delete_many({"Sender": data["user_id"]})
        return {"status": "success"}, 200
        
    elif mode == "setComplete":
        db.status.update_one({"Id": data["user_id"]}, {"$set": {"ProfComplete": 1}})
        db.status.update_one({"Id": data["user_id"]}, {"$inc": {"PtsEx": 5, "PtsTotal": 5}})
        db.activity.update_one({"Id": data["user_id"]}, {"$set": {"Has_Completed_Course": 1}})
        return {"status": "success"}, 200
    
    elif mode == "setLoggedIn":
        db.activity.update_one({"Id": data["user_id"]}, {"$set": {"Is_logged_In": 1}})
        return {"status": "success"}, 200
    elif mode == "incDay":
        db.activity.update_one({"Id": data["user_id"]}, {"$inc": {"Day": 1}})
        return {"status": "success"}, 200
    elif mode == "returnleaderboard":
        leaderboard = db.activity.find().sort("PtsTotal", -1).limit(10)
        return {"leaderboard": leaderboard}

    elif mode == "setPublic":
        courseID = data["courseID"]
        a = db.explorer.update_one({"courseID": courseID, "user_id": data["user_id"]}, {"$set": {"is_public": True}})
        if a.matched_count == 0:
            return {"error": "Course not found or not accessible"}, 404
        return {"status": "success"}, 200
    
    elif mode == "setPrivate":
        courseID = data["courseID"]
        a = db.explorer.update_one({"courseID": courseID, "user_id": data["user_id"]}, {"$set": {"is_public": False}})
        if a.matched_count == 0:
            return {"error": "Course not found or not accessible"}, 404
        return {"status": "success"}, 200


@app.route("/", methods = ['GET'])
def index():
    return "Ahis"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)