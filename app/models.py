from . import db

class Aadhaar(db.Model):
    __tablename__ = "aadhaar"
    aadhaarNo = db.Column(db.String(12), primary_key=True)
    name = db.Column(db.String(100))
    address = db.Column(db.Text)
    mobileNo = db.Column(db.String(15))
    category = db.Column(db.String(50))
    face_image = db.Column(db.LargeBinary)  # store raw JPG bytes

  
class GeneralCount(db.Model):
    aadhaarNo = db.Column(db.String(12),db.ForeignKey('aadhaar.aadhaarNo'),primary_key=True)
    count = db.Column(db.Integer)

    def __init__(self,aadhaarNo,count):
        self.aadhaarNo = aadhaarNo
        self.count = count

class Entitlement(db.Model):
    category = db.Column(db.String(3),primary_key=True)
    maxAmount = db.Column(db.Integer)

    def __init__(self,category,maxAmount):
        self.category = category
        self.maxAmount = maxAmount



