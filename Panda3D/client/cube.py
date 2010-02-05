from panda3d.core import GeomVertexFormat, GeomVertexData
from panda3d.core import Geom, GeomTriangles, GeomVertexWriter
from panda3d.core import Texture, GeomNode
from panda3d.core import Vec3, Vec4, Point3

def makeSquare(x1,y1,z1, x2,y2,z2):
	format=GeomVertexFormat.getV3n3cpt2()
	vdata=GeomVertexData('square', format, Geom.UHDynamic)

	vertex=GeomVertexWriter(vdata, 'vertex')
	normal=GeomVertexWriter(vdata, 'normal')
	color=GeomVertexWriter(vdata, 'color')
	texcoord=GeomVertexWriter(vdata, 'texcoord')
	
	#make sure we draw the sqaure in the right plane
	if x1!=x2:
		vertex.addData3f(x1, y1, z1)
		vertex.addData3f(x2, y1, z1)
		vertex.addData3f(x2, y2, z2)
		vertex.addData3f(x1, y2, z2)

		normal.addData3f(myNormalize(Vec3(2*x1-1, 2*y1-1, 2*z1-1)))
		normal.addData3f(myNormalize(Vec3(2*x2-1, 2*y1-1, 2*z1-1)))
		normal.addData3f(myNormalize(Vec3(2*x2-1, 2*y2-1, 2*z2-1)))
		normal.addData3f(myNormalize(Vec3(2*x1-1, 2*y2-1, 2*z2-1)))
		
	else:
		vertex.addData3f(x1, y1, z1)
		vertex.addData3f(x2, y2, z1)
		vertex.addData3f(x2, y2, z2)
		vertex.addData3f(x1, y1, z2)

		normal.addData3f(myNormalize(Vec3(2*x1-1, 2*y1-1, 2*z1-1)))
		normal.addData3f(myNormalize(Vec3(2*x2-1, 2*y2-1, 2*z1-1)))
		normal.addData3f(myNormalize(Vec3(2*x2-1, 2*y2-1, 2*z2-1)))
		normal.addData3f(myNormalize(Vec3(2*x1-1, 2*y1-1, 2*z2-1)))

	#adding different colors to the vertex for visibility
	color.addData4f(1.0,0.0,0.0,1.0)
	color.addData4f(0.0,1.0,0.0,1.0)
	color.addData4f(0.0,0.0,1.0,1.0)
	color.addData4f(1.0,0.0,1.0,1.0)

	texcoord.addData2f(0.0, 1.0)
	texcoord.addData2f(0.0, 0.0)
	texcoord.addData2f(1.0, 0.0)
	texcoord.addData2f(1.0, 1.0)

	#quads arent directly supported by the Geom interface
	#you might be interested in the CardMaker class if you are
	#interested in rectangle though
	tri1=GeomTriangles(Geom.UHDynamic)
	tri2=GeomTriangles(Geom.UHDynamic)

	tri1.addVertex(0)
	tri1.addVertex(1)
	tri1.addVertex(3)

	tri2.addConsecutiveVertices(1,3)

	tri1.closePrimitive()
	tri2.closePrimitive()


	square=Geom(vdata)
	square.addPrimitive(tri1)
	square.addPrimitive(tri2)
	
	return square

def myNormalize(myVec):
	myVec.normalize()
	return myVec

def makeCube(size, id):
    size = size/2
    square0=makeSquare(-size,-size,-size, size,-size, size)
    square1=makeSquare(-size, size,-size, size, size, size)
    square2=makeSquare(-size, size, size, size,-size, size)
    square3=makeSquare(-size, size,-size, size,-size,-size)
    square4=makeSquare(-size,-size,-size,-size, size, size)
    square5=makeSquare( size,-size,-size, size, size, size)
    snode=GeomNode(id)
    snode.addGeom(square0)
    snode.addGeom(square1)
    snode.addGeom(square2)
    snode.addGeom(square3)
    snode.addGeom(square4)
    snode.addGeom(square5)
    return snode