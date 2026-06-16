from UPMP import Animation, idaStar, stackAreaGenerator, accessDirectionFixing

area = stackAreaGenerator(5,5,3,40,"NSWE",5)
lanes, lane = accessDirectionFixing(area)
result = idaStar(lane)
Animation(result, area, lanes, lane)





